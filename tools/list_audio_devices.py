#!/usr/bin/python3
# -*- coding: utf-8 -*-

import crcengine
import sounddevice as sd
import multiprocessing

def list_audio_devices():
    input_audio = []
    output_audio = []
    fetch_audio_devices(input_audio,output_audio)
    
    print ("-------------------- Input (RX) Audio Devices ----------------------------")
    print ("[ID]\t[CRC]\t " + "[Name]".ljust(50) + "[API]")
    for device in (input_audio):
        print(str(device["native_index"]) + "\t" + device["id"] +  "\t" + device["name"].strip().ljust(50) +  device["api"])
    
    print ("\n-------------------- Output (TX) Audio Devices ----------------------------")
    print ("[ID]\t[CRC]\t " + "[Name]".ljust(50) + "[API]")
    for device in (output_audio):
        print(str(device["native_index"]) + "\t" + device["id"] + " \t " + device["name"].strip().ljust(50) + device["api"])

def device_crc(device) -> str:
    crc_hwid = crc_algorithm(bytes(f"{device}", encoding="utf-8"))
    crc_hwid = crc_hwid.to_bytes(2, byteorder="big")
    crc_hwid = crc_hwid.hex()
    return crc_hwid

def get_audio_devices():
    """
    return list of input and output audio devices in own process to avoid crashes of portaudio on raspberry pi

    also uses a process data manager
    """
    # we need to run this on Windows for multiprocessing support
    # multiprocessing.freeze_support()
    # multiprocessing.get_context("spawn")

    # we need to reset and initialize sounddevice before running the multiprocessing part.
    # If we are not doing this at this early point, not all devices will be displayed
    sd._terminate()
    sd._initialize()

    # log.debug("[AUD] get_audio_devices")
    with multiprocessing.Manager() as manager:
        proxy_input_devices = manager.list()
        proxy_output_devices = manager.list()
        # print(multiprocessing.get_start_method())
        proc = multiprocessing.Process(
            target=fetch_audio_devices, args=(proxy_input_devices, proxy_output_devices)
        )
        proc.start()
        proc.join()

        # additional logging for audio devices
        # log.debug("[AUD] get_audio_devices: input_devices:", list=f"{proxy_input_devices}")
        # log.debug("[AUD] get_audio_devices: output_devices:", list=f"{proxy_output_devices}")
        return list(proxy_input_devices), list(proxy_output_devices)

def fetch_audio_devices(input_devices, output_devices):
    """
    get audio devices from portaudio

    Args:
      input_devices: proxy variable for input devices
      output_devices: proxy variable for output devices

    Returns:

    """
    devices = sd.query_devices(device=None, kind=None)

    for index, device in enumerate(devices):
        # Use a try/except block because Windows doesn't have an audio device range
        try:
            name = device["name"]
            # Ignore some Flex Radio devices to make device selection simpler
            if name.startswith("DAX RESERVED") or name.startswith("DAX IQ"):
                continue

            max_output_channels = device["max_output_channels"]
            max_input_channels = device["max_input_channels"]

        except KeyError:
            continue
        except Exception as err:
            print(err)
            max_input_channels = 0
            max_output_channels = 0

        if max_input_channels > 0:
            hostapi_name = sd.query_hostapis(device['hostapi'])['name']

            new_input_device = {"id": device_crc(device), 
                                "name": device['name'], 
                                "api": hostapi_name,
                                "native_index":index}
            # check if device not in device list
            if new_input_device not in input_devices:
                input_devices.append(new_input_device)

        if max_output_channels > 0:
            hostapi_name = sd.query_hostapis(device['hostapi'])['name']
            new_output_device = {"id": device_crc(device), 
                                 "name": device['name'], 
                                 "api": hostapi_name,
                                 "native_index":index}
            # check if device not in device list
            if new_output_device not in output_devices:
                output_devices.append(new_output_device)


crc_algorithm = crcengine.new("crc16-ccitt-false")  # load crc16 library
list_audio_devices()
