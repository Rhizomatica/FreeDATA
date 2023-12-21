#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 23 07:04:24 2020

@author: DJ2LS
"""

# pylint: disable=invalid-name, line-too-long, c-extension-no-member
# pylint: disable=import-outside-toplevel

import atexit
import ctypes
import queue
import threading
import time
import codec2
import numpy as np
import sounddevice as sd
import structlog
import tci
import cw
from queues import RIGCTLD_COMMAND_QUEUE
import audio
import event_manager
import demodulator

TESTMODE = False

class RF:
    """Class to encapsulate interactions between the audio device and codec2"""

    log = structlog.get_logger("RF")

    def __init__(self, config, event_queue, fft_queue, service_queue, states) -> None:
        self.config = config
        print(config)
        self.service_queue = service_queue
        self.states = states

        self.sampler_avg = 0
        self.buffer_avg = 0

        # these are crc ids now
        self.audio_input_device = config['AUDIO']['input_device']
        self.audio_output_device = config['AUDIO']['output_device']

        self.tx_audio_level = config['AUDIO']['tx_audio_level']
        self.enable_audio_auto_tune = config['AUDIO']['enable_auto_tune']
        self.tx_delay = config['MODEM']['tx_delay']

        self.radiocontrol = config['RADIO']['control']
        self.rigctld_ip = config['RIGCTLD']['ip']
        self.rigctld_port = config['RIGCTLD']['port']

        self.states.setTransmitting(False)

        self.ptt_state = False
        self.radio_alc = 0.0

        self.tci_ip = config['TCI']['tci_ip']
        self.tci_port = config['TCI']['tci_port']


        self.AUDIO_SAMPLE_RATE = 48000
        self.MODEM_SAMPLE_RATE = codec2.api.FREEDV_FS_8000

        # 8192 Let's do some tests with very small chunks for TX
        self.AUDIO_FRAMES_PER_BUFFER_TX = 1200 if self.radiocontrol in ["tci"] else 2400 * 2
        # 8 * (self.AUDIO_SAMPLE_RATE/self.MODEM_SAMPLE_RATE) == 48
        self.AUDIO_CHANNELS = 1
        self.MODE = 0

        # Locking state for mod out so buffer will be filled before we can use it
        # https://github.com/DJ2LS/FreeDATA/issues/127
        # https://github.com/DJ2LS/FreeDATA/issues/99
        self.mod_out_locked = True
        self.rms_counter = 0

        # Make sure our resampler will work
        assert (self.AUDIO_SAMPLE_RATE / self.MODEM_SAMPLE_RATE) == codec2.api.FDMDV_OS_48  # type: ignore

        self.modem_transmit_queue = queue.Queue()
        self.modem_received_queue = queue.Queue()

        self.audio_received_queue = queue.Queue()

        self.data_queue_received = queue.Queue()

        self.event_manager = event_manager.EventManager([event_queue])

        self.fft_queue = fft_queue

        self.demodulator = demodulator.Demodulator(self.config, 
                                            self.audio_received_queue, 
                                            self.modem_received_queue,
                                            self.data_queue_received,
                                            self.states,
                                            self.event_manager,
                                            self.fft_queue
                                                   )



    def tci_tx_callback(self, audio_48k) -> None:
        self.radio.set_ptt(True)
        self.event_manager.send_ptt_change(True)
        self.tci_module.push_audio(audio_48k)

    def start_modem(self):
        # testmode: We need to call the modem without audio parts for running protocol tests

        if self.radiocontrol not in ["tci"]:
            result = self.init_audio() if not TESTMODE else True
            if not result:
                raise RuntimeError("Unable to init audio devices")
            if not TESTMODE:
                self.demodulator.start(self.sd_input_stream)

        else:
            result = self.init_tci()

        if result not in [False]:
            # init codec2 instances
            self.init_codec2()

            # init rig control
            self.init_rig_control()

            # init data thread
            self.init_data_threads()
            if not TESTMODE:
                atexit.register(self.sd_input_stream.stop)

        else:
            return False

    def stop_modem(self):
        try:
            # let's stop the modem service
            self.service_queue.put("stop")
            # simulate audio class active state for reducing cli output
            # self.stream = lambda: None
            # self.stream.active = False
            # self.stream.stop

        except Exception:
            self.log.error("[MDM] Error stopping modem")

    def init_audio(self):
        self.log.info(f"[MDM] init: get audio devices", input_device=self.audio_input_device,
                      output_device=self.audio_output_device)
        try:
            result = audio.get_device_index_from_crc(self.audio_input_device, True)
            if result is None:
                raise ValueError("Invalid input device")
            else:
                in_dev_index, in_dev_name = result

            result = audio.get_device_index_from_crc(self.audio_output_device, False)
            if result is None:
                raise ValueError("Invalid output device")
            else:
                out_dev_index, out_dev_name = result

            self.log.info(f"[MDM] init: receiving audio from '{in_dev_name}'")
            self.log.info(f"[MDM] init: transmiting audio on '{out_dev_name}'")
            self.log.debug("[MDM] init: starting pyaudio callback and decoding threads")

            sd.default.samplerate = self.AUDIO_SAMPLE_RATE
            sd.default.device = (in_dev_index, out_dev_index)

            # init codec2 resampler
            self.resampler = codec2.resampler()

            # SoundDevice audio input stream
            self.sd_input_stream = sd.InputStream(
                channels=1,
                dtype="int16",
                callback=self.demodulator.sd_input_audio_callback,
                device=in_dev_index,
                samplerate=self.AUDIO_SAMPLE_RATE,
                blocksize=4800,
            )
            self.sd_input_stream.start()

            return True



        except Exception as audioerr:
            self.log.error("[MDM] init: starting pyaudio callback failed", e=audioerr)
            self.stop_modem()
            return False

    def init_tci(self):
        # placeholder area for processing audio via TCI
        # https://github.com/maksimus1210/TCI
        self.log.warning("[MDM] [TCI] Not yet fully implemented", ip=self.tci_ip, port=self.tci_port)

        # we are trying this by simulating an audio stream Object like with mkfifo
        class Object:
            """An object for simulating audio stream"""
            active = True

        self.stream = Object()

        # lets init TCI module
        self.tci_module = tci.TCICtrl(self.audio_received_queue)

        # let's start the audio tx callback
        self.log.debug("[MDM] Starting tci tx callback thread")
        tci_tx_callback_thread = threading.Thread(
            target=self.tci_tx_callback,
            name="TCI TX CALLBACK THREAD",
            daemon=True,
        )
        tci_tx_callback_thread.start()
        return True

    def audio_auto_tune(self):
        # enable / disable AUDIO TUNE Feature / ALC correction
        if self.enable_audio_auto_tune:
            if self.radio_alc == 0.0:
                self.tx_audio_level = self.tx_audio_level + 20
            elif 0.0 < self.radio_alc <= 0.1:
                print("0.0 < self.radio_alc <= 0.1")
                self.tx_audio_level = self.tx_audio_level + 2
                self.log.debug("[MDM] AUDIO TUNE", audio_level=str(self.tx_audio_level),
                               alc_level=str(self.radio_alc))
            elif 0.1 < self.radio_alc < 0.2:
                print("0.1 < self.radio_alc < 0.2")
                self.tx_audio_level = self.tx_audio_level
                self.log.debug("[MDM] AUDIO TUNE", audio_level=str(self.tx_audio_level),
                               alc_level=str(self.radio_alc))
            elif 0.2 < self.radio_alc < 0.99:
                print("0.2 < self.radio_alc < 0.99")
                self.tx_audio_level = self.tx_audio_level - 20
                self.log.debug("[MDM] AUDIO TUNE", audio_level=str(self.tx_audio_level),
                               alc_level=str(self.radio_alc))
            elif 1.0 >= self.radio_alc:
                print("1.0 >= self.radio_alc")
                self.tx_audio_level = self.tx_audio_level - 40
                self.log.debug("[MDM] AUDIO TUNE", audio_level=str(self.tx_audio_level),
                               alc_level=str(self.radio_alc))
            else:
                self.log.debug("[MDM] AUDIO TUNE", audio_level=str(self.tx_audio_level),
                               alc_level=str(self.radio_alc))

    def transmit(
            self, mode, repeats: int, repeat_delay: int, frames: bytearray
    ) -> bool:
        """

        Args:
          mode:
          repeats:
          repeat_delay:
          frames:

        """
        if TESTMODE:
            return


        self.demodulator.reset_data_sync()
        # get freedv instance by mode
        mode_transition = {
            codec2.FREEDV_MODE.signalling: self.freedv_datac13_tx,
            codec2.FREEDV_MODE.datac0: self.freedv_datac0_tx,
            codec2.FREEDV_MODE.datac1: self.freedv_datac1_tx,
            codec2.FREEDV_MODE.datac3: self.freedv_datac3_tx,
            codec2.FREEDV_MODE.datac4: self.freedv_datac4_tx,
            codec2.FREEDV_MODE.datac13: self.freedv_datac13_tx,
        }
        if mode in mode_transition:
            freedv = mode_transition[mode]
        else:
            print("wrong mode.................")
            print(mode)
            return False

        # Wait for some other thread that might be transmitting
        self.states.waitForTransmission()
        self.states.setTransmitting(True)
        # if we're transmitting FreeDATA signals, reset channel busy state
        self.states.set("channel_busy", False)

        start_of_transmission = time.time()
        # TODO Moved ptt toggle some steps before audio is ready for testing
        # Toggle ptt early to save some time and send ptt state via socket
        # self.radio.set_ptt(True)
        # jsondata = {"ptt": "True"}
        # data_out = json.dumps(jsondata)
        # sock.SOCKET_QUEUE.put(data_out)

        # Open codec2 instance
        self.MODE = mode

        # Get number of bytes per frame for mode
        bytes_per_frame = int(codec2.api.freedv_get_bits_per_modem_frame(freedv) / 8)
        payload_bytes_per_frame = bytes_per_frame - 2

        # Init buffer for data
        n_tx_modem_samples = codec2.api.freedv_get_n_tx_modem_samples(freedv)
        mod_out = ctypes.create_string_buffer(n_tx_modem_samples * 2)

        # Init buffer for preample
        n_tx_preamble_modem_samples = codec2.api.freedv_get_n_tx_preamble_modem_samples(
            freedv
        )
        mod_out_preamble = ctypes.create_string_buffer(n_tx_preamble_modem_samples * 2)

        # Init buffer for postamble
        n_tx_postamble_modem_samples = (
            codec2.api.freedv_get_n_tx_postamble_modem_samples(freedv)
        )
        mod_out_postamble = ctypes.create_string_buffer(
            n_tx_postamble_modem_samples * 2
        )

        # Add empty data to handle ptt toggle time
        if self.tx_delay > 0:
            data_delay = int(self.MODEM_SAMPLE_RATE * (self.tx_delay / 1000))  # type: ignore
            mod_out_silence = ctypes.create_string_buffer(data_delay * 2)
            txbuffer = bytes(mod_out_silence)
        else:
            txbuffer = bytes()

        self.log.debug(
            "[MDM] TRANSMIT", mode=self.MODE, payload=payload_bytes_per_frame, delay=self.tx_delay
        )

        if not isinstance(frames, list): frames = [frames]
        for _ in range(repeats):

            # Create modulation for all frames in the list
            for frame in frames:

                # Write preamble to txbuffer
                codec2.api.freedv_rawdatapreambletx(freedv, mod_out_preamble)
                txbuffer += bytes(mod_out_preamble)

                # Create buffer for data
                # Use this if CRC16 checksum is required (DATAc1-3)
                buffer = bytearray(payload_bytes_per_frame)
                # Set buffersize to length of data which will be send
                buffer[: len(frame)] = frame  # type: ignore

                # Create crc for data frame -
                #   Use the crc function shipped with codec2
                #   to avoid CRC algorithm incompatibilities
                # Generate CRC16
                crc = ctypes.c_ushort(
                    codec2.api.freedv_gen_crc16(bytes(buffer), payload_bytes_per_frame)
                )
                # Convert crc to 2-byte (16-bit) hex string
                crc = crc.value.to_bytes(2, byteorder="big")
                # Append CRC to data buffer
                buffer += crc

                assert(bytes_per_frame == len(buffer))
                data = (ctypes.c_ubyte * bytes_per_frame).from_buffer_copy(buffer)
                # modulate DATA and save it into mod_out pointer
                codec2.api.freedv_rawdatatx(freedv, mod_out, data)
                txbuffer += bytes(mod_out)

                # Write postamble to txbuffer
                codec2.api.freedv_rawdatapostambletx(freedv, mod_out_postamble)
                # Append postamble to txbuffer
                txbuffer += bytes(mod_out_postamble)

            # Add delay to end of frames
            samples_delay = int(self.MODEM_SAMPLE_RATE * (repeat_delay / 1000))  # type: ignore
            mod_out_silence = ctypes.create_string_buffer(samples_delay * 2)
            txbuffer += bytes(mod_out_silence)

        # Re-sample back up to 48k (resampler works on np.int16)
        x = np.frombuffer(txbuffer, dtype=np.int16)

        self.audio_auto_tune()
        x = audio.set_audio_volume(x, self.tx_audio_level)

        if not self.radiocontrol in ["tci"]:
            txbuffer_out = self.resampler.resample8_to_48(x)
        else:
            txbuffer_out = x

        # Explicitly lock our usage of mod_out_queue if needed
        # This could avoid audio problems on slower CPU
        # we will fill our modout list with all data, then start
        # processing it in audio callback
        self.mod_out_locked = True

        # -------------------------------
        # add modulation to modout_queue
        self.transmit_audio(txbuffer_out)

        # Release our mod_out_lock, so we can use the queue
        self.mod_out_locked = False

        # we need to wait manually for tci processing
        if self.radiocontrol in ["tci"]:
            duration = len(txbuffer_out) / 8000
            timestamp_to_sleep = time.time() + duration
            self.log.debug("[MDM] TCI calculated duration", duration=duration)
            tci_timeout_reached = False
            #while time.time() < timestamp_to_sleep:
            #    threading.Event().wait(0.01)
        else:
            timestamp_to_sleep = time.time()
            # set tci timeout reached to True for overriding if not used
            tci_timeout_reached = True

        while not tci_timeout_reached:
            if self.radiocontrol in ["tci"]:
                if time.time() < timestamp_to_sleep:
                    tci_timeout_reached = False
                else:
                    tci_timeout_reached = True
            threading.Event().wait(0.01)
            # if we're transmitting FreeDATA signals, reset channel busy state
            self.states.set("channel_busy", False)

        self.radio.set_ptt(False)

        # Push ptt state to socket stream
        self.event_manager.send_ptt_change(False)

        # After processing, set the locking state back to true to be prepared for next transmission
        self.mod_out_locked = True

        self.states.setTransmitting(False)

        end_of_transmission = time.time()
        transmission_time = end_of_transmission - start_of_transmission
        self.log.debug("[MDM] ON AIR TIME", time=transmission_time)
        return True

    def transmit_morse(self, repeats, repeat_delay, frames):
        self.states.waitForTransmission()
        self.states.setTransmitting(True)
        # if we're transmitting FreeDATA signals, reset channel busy state
        self.states.set("channel_busy", False)
        self.log.debug(
            "[MDM] TRANSMIT", mode="MORSE"
        )
        start_of_transmission = time.time()

        txbuffer_out = cw.MorseCodePlayer().text_to_signal("DJ2LS-1")

        self.mod_out_locked = True
        self.transmit_audio(txbuffer_out)
        self.mod_out_locked = False

        # we need to wait manually for tci processing
        if self.radiocontrol in ["tci"]:
            duration = len(txbuffer_out) / 8000
            timestamp_to_sleep = time.time() + duration
            self.log.debug("[MDM] TCI calculated duration", duration=duration)
            tci_timeout_reached = False
            #while time.time() < timestamp_to_sleep:
            #    threading.Event().wait(0.01)
        else:
            timestamp_to_sleep = time.time()
            # set tci timeout reached to True for overriding if not used
            tci_timeout_reached = True

        while not tci_timeout_reached:
            if self.radiocontrol in ["tci"]:
                if time.time() < timestamp_to_sleep:
                    tci_timeout_reached = False
                else:
                    tci_timeout_reached = True

            threading.Event().wait(0.01)
            # if we're transmitting FreeDATA signals, reset channel busy state
            self.states.set("channel_busy", False)

        self.radio.set_ptt(False)

        # Push ptt state to socket stream
        self.event_manager.send_ptt_change(False)

        # After processing, set the locking state back to true to be prepared for next transmission
        self.mod_out_locked = True

        self.modem_transmit_queue.task_done()
        self.states.setTransmitting(False)

        end_of_transmission = time.time()
        transmission_time = end_of_transmission - start_of_transmission
        self.log.debug("[MDM] ON AIR TIME", time=transmission_time)

    def init_codec2(self):
        # Open codec2 instances

        # INIT TX MODES - here we need all modes. 
        self.freedv_datac0_tx = codec2.open_instance(codec2.FREEDV_MODE.datac0.value)
        self.freedv_datac1_tx = codec2.open_instance(codec2.FREEDV_MODE.datac1.value)
        self.freedv_datac3_tx = codec2.open_instance(codec2.FREEDV_MODE.datac3.value)
        self.freedv_datac4_tx = codec2.open_instance(codec2.FREEDV_MODE.datac4.value)
        self.freedv_datac13_tx = codec2.open_instance(codec2.FREEDV_MODE.datac13.value)

    def init_data_threads(self):
        worker_received = threading.Thread(
            target=self.demodulator.worker_received, name="WORKER_THREAD", daemon=True
        )
        worker_received.start()

    # Low level modem audio transmit
    def transmit_audio(self, audio_48k) -> None:
        self.radio.set_ptt(True)
        self.event_manager.send_ptt_change(True)

        if self.radiocontrol in ["tci"]:
            self.tci_tx_callback(audio_48k)
        else:
            sd.play(audio_48k, blocking=True)
        return

    def init_rig_control(self):
        # Check how we want to control the radio
        if self.radiocontrol == "rigctld":
            import rigctld as rig
        elif self.radiocontrol == "tci":
            self.radio = self.tci_module
        else:
            import rigdummy as rig

        if not self.radiocontrol in ["tci"]:
            self.radio = rig.radio()
            self.radio.open_rig(
                rigctld_ip=self.rigctld_ip,
                rigctld_port=self.rigctld_port,
            )
        hamlib_thread = threading.Thread(
            target=self.update_rig_data, name="HAMLIB_THREAD", daemon=True
        )
        hamlib_thread.start()

        hamlib_set_thread = threading.Thread(
            target=self.set_rig_data, name="HAMLIB_SET_THREAD", daemon=True
        )
        hamlib_set_thread.start()

    def set_rig_data(self) -> None:
        """
            Set rigctld parameters like frequency, mode
            THis needs to be processed in a queue
        """
        while True:
            cmd = RIGCTLD_COMMAND_QUEUE.get()
            if cmd[0] == "set_frequency":
                # [1] = Frequency
                self.radio.set_frequency(cmd[1])
            if cmd[0] == "set_mode":
                # [1] = Mode
                self.radio.set_mode(cmd[1])

    def update_rig_data(self) -> None:
        """
        Request information about the current state of the radio via hamlib
        """
        while True:
            try:
                # this looks weird, but is necessary for avoiding rigctld packet colission sock
                #threading.Event().wait(0.1)
                self.states.set("radio_status", self.radio.get_status())
                #threading.Event().wait(0.25)
                self.states.set("radio_frequency", self.radio.get_frequency())
                threading.Event().wait(0.1)
                self.states.set("radio_mode", self.radio.get_mode())
                threading.Event().wait(0.1)
                self.states.set("radio_bandwidth", self.radio.get_bandwidth())
                threading.Event().wait(0.1)
                if self.states.isTransmitting():
                    self.radio_alc = self.radio.get_alc()
                    threading.Event().wait(0.1)
                self.states.set("radio_rf_power", self.radio.get_level())
                threading.Event().wait(0.1)
                self.states.set("radio_strength", self.radio.get_strength())

            except Exception as e:
                self.log.warning(
                    "[MDM] error getting radio data",
                    e=e,
                )
                threading.Event().wait(1)

