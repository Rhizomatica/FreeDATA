#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec 25 21:25:14 2020

@author: DJ2LS
"""

import time
import logging
import asyncio
import crcengine


import static
import data_handler

def wait(seconds):
    timeout = time.time() + seconds
    
    while time.time() < timeout:
        time.sleep(0.01)
        
        

def get_crc_8(data):
    """
    Author: DJ2LS

    Get the CRC8 of a byte string

    param: data = bytes()
    """
    crc_algorithm = crcengine.new('crc8-ccitt')  # load crc8 library
    crc_data = crc_algorithm(data)
    crc_data = crc_data.to_bytes(1, byteorder='big')
    return crc_data


def get_crc_16(data):
    """
    Author: DJ2LS

    Get the CRC16 of a byte string

    param: data = bytes()
    """
    crc_algorithm = crcengine.new('crc16-ccitt-false')  # load crc16 library
    crc_data = crc_algorithm(data)
    crc_data = crc_data.to_bytes(2, byteorder='big')
    return crc_data

def watchdog():
    """
    Author: DJ2LS
    
    watchdog master function. Frome here we call the watchdogs
    """
    while True:
        time.sleep(0.01)
        data_channel_keep_alive_watchdog()

def data_channel_keep_alive_watchdog():
    """
    Author: DJ2LS
    
   
    """

    if static.ARQ_STATE == 'DATA' and static.TNC_STATE == 'BUSY': # and not static.ARQ_SEND_KEEP_ALIVE:
        time.sleep(0.01)
        if static.ARQ_DATA_CHANNEL_LAST_RECEIVED + 30 > time.time():
            pass
        else:
            static.ARQ_DATA_CHANNEL_LAST_RECEIVED = 0
            logging.info("DATA [" + str(static.MYCALLSIGN, 'utf-8') + "]<<T>>[" + str(static.DXCALLSIGN, 'utf-8') + "] [BER." + str(static.BER) + "]")
            arq_reset_frame_machine()


def arq_reset_timeout(state):
    """
    Author: DJ2LS
    """
    static.ARQ_RX_ACK_TIMEOUT = state
    static.ARQ_RX_FRAME_TIMEOUT = state
    static.ARQ_RX_RPT_TIMEOUT = state


def arq_reset_ack(state):
    """
    Author: DJ2LS
    """
    static.ARQ_ACK_RECEIVED = state
    static.ARQ_RPT_RECEIVED = state
    static.ARQ_FRAME_ACK_RECEIVED = state


def arq_reset_frame_machine():
    """
    Author: DJ2LS

    Reset the frame machine parameters to default,
    so we need to call just a function

    """
    arq_reset_timeout(False)
    arq_reset_ack(False)
    static.TX_N_RETRIES = 0
    static.ARQ_N_SENT_FRAMES = 0
    static.ARQ_TX_N_FRAMES_PER_BURST = 0
    static.ARQ_TX_N_CURRENT_ARQ_FRAME = 0
    static.ARQ_TX_N_TOTAL_ARQ_FRAMES = 0
    static.ARQ_TX_N_CURRENT_ARQ_FRAME = 0

    static.ARQ_RX_N_CURRENT_ARQ_FRAME = 0
    static.ARQ_N_ARQ_FRAMES_PER_DATA_FRAME = 0
    static.ARQ_FRAME_BOF_RECEIVED = False
    static.ARQ_FRAME_EOF_RECEIVED = False
    
    static.ARQ_RX_BURST_BUFFER = []
    static.ARQ_RX_FRAME_BUFFER = []
    
    static.TNC_STATE = 'IDLE'
    static.ARQ_STATE = 'IDLE'
    ###static.ARQ_CONNECTION_KEEP_ALIVE_RECEIVED = int(time.time()) # we need to reset the counter at this point
    ###static.ARQ_SEND_KEEP_ALIVE = True
    static.CHANNEL_STATE = 'RECEIVING_SIGNALLING'
    static.ARQ_READY_FOR_DATA = False

    static.ARQ_START_OF_TRANSMISSION = 0

def calculate_transfer_rate():
    if static.ARQ_START_OF_TRANSMISSION > 0:
        static.TOTAL_TRANSMISSION_TIME = time.time() - static.ARQ_START_OF_TRANSMISSION


    print("ARQ_N_ARQ_FRAMES_PER_DATA_FRAME " + str(static.ARQ_N_ARQ_FRAMES_PER_DATA_FRAME))
    print("ARQ_RX_N_CURRENT_ARQ_FRAME " + str(static.ARQ_RX_N_CURRENT_ARQ_FRAME))



    arq_n_arq_frames_per_data_frame = static.ARQ_N_ARQ_FRAMES_PER_DATA_FRAME
    arq_rx_n_current_arq_frame = static.ARQ_RX_N_CURRENT_ARQ_FRAME
   
    if static.TX_BUFFER_SIZE == 0:
        total_n_frames = arq_n_arq_frames_per_data_frame
    elif arq_n_arq_frames_per_data_frame == 0:
        total_n_frames = static.TX_BUFFER_SIZE
    else:
        total_n_frames = 0
        
    if static.TOTAL_TRANSMISSION_TIME > 0:
        #total_transmission_time = time.time() - static.ARQ_START_OF_TRANSMISSION
        total_transmission_time = static.TOTAL_TRANSMISSION_TIME 
        print("total_transmission_time: " + str(total_transmission_time))  
        print("static.TOTAL_BYTES: " + str(static.TOTAL_BYTES))
   


        static.ARQ_BITS_PER_SECOND = int((static.TOTAL_BYTES * 8) / total_transmission_time)
        static.ARQ_BYTES_PER_MINUTE = int(((static.TOTAL_BYTES) / total_transmission_time) * 60)
      
        burst_bytes = static.ARQ_PAYLOAD_PER_FRAME * static.ARQ_N_RX_FRAMES_PER_BURSTS
        burst_transmission_time = time.time() - static.ARQ_START_OF_BURST
        print("BURST TRANSMISSION TIME: " + str(burst_transmission_time))
        static.ARQ_BITS_PER_SECOND_BURST = int((burst_bytes * 8) / burst_transmission_time)
        static.ARQ_BYTES_PER_MINUTE_BURST = int(((burst_bytes) / burst_transmission_time) * 60)
        print("static.ARQ_BITS_PER_SECOND_BURST: " + str(static.ARQ_BITS_PER_SECOND_BURST))
        print("static.ARQ_BYTES_PER_MINUTE_BURST: " + str(static.ARQ_BYTES_PER_MINUTE_BURST))
  
    # PERCENTAGE FOR TRANSMITTING
    if static.TX_BUFFER_SIZE > 0:
        print("static.ARQ_N_SENT_FRAMES: " + str(static.ARQ_N_SENT_FRAMES))
        static.ARQ_TRANSMISSION_PERCENT = int((static.ARQ_N_SENT_FRAMES / static.TX_BUFFER_SIZE) * 100)

    # PERCENTAGE FOR RECEIVING
    elif arq_n_arq_frames_per_data_frame > 0:
        static.ARQ_TRANSMISSION_PERCENT = int((static.ARQ_RX_N_CURRENT_ARQ_FRAME / static.ARQ_N_ARQ_FRAMES_PER_DATA_FRAME) * 100)
    
    else:
        static.ARQ_TRANSMISSION_PERCENT = 0.0   
   
    print("static.ARQ_TRANSMISSION_PERCENT: " + str(static.ARQ_TRANSMISSION_PERCENT))
    print("static.ARQ_BYTES_PER_MINUTE: " + str(static.ARQ_BYTES_PER_MINUTE))
    print("static.ARQ_BITS_PER_SECOND: " + str(static.ARQ_BITS_PER_SECOND))
    return [static.ARQ_BITS_PER_SECOND, static.ARQ_BYTES_PER_MINUTE, static.ARQ_BITS_PER_SECOND_BURST, static.ARQ_BYTES_PER_MINUTE_BURST]
               

def add_to_heard_stations(dxcallsign,dxgrid, datatype, snr):
    # check if buffer empty
    if len(static.HEARD_STATIONS) == 0:
        static.HEARD_STATIONS.append([dxcallsign,dxgrid, int(time.time()), datatype, snr])
    # if not, we search and update
    else:
        for i in range(0, len(static.HEARD_STATIONS)):
            # update callsign with new timestamp
            if static.HEARD_STATIONS[i].count(dxcallsign) > 0:
                static.HEARD_STATIONS[i] = [dxcallsign,dxgrid, int(time.time()), datatype, snr]
                break
            # insert if nothing found
            if i == len(static.HEARD_STATIONS) - 1:
                static.HEARD_STATIONS.append([dxcallsign,dxgrid, int(time.time()), datatype, snr])
                break
                
                
#    for idx, item in enumerate(static.HEARD_STATIONS):
#        if dxcallsign in item:
#            item = [dxcallsign, int(time.time())]
#            static.HEARD_STATIONS[idx] = item                
                
def setup_logging():
    """
    Author: DJ2LS

    Set the custom logging format so we can use colors
    
    # https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
    # 'DEBUG'   : 37, # white
    # 'INFO'    : 36, # cyan
    # 'WARNING' : 33, # yellow
    # 'ERROR'   : 31, # red
    # 'CRITICAL': 41, # white on red bg
    
    """

    logging.basicConfig(level=logging.INFO, \
        encoding='utf-8', \
        format='%(asctime)s.%(msecs)03d %(levelname)s:\t%(message)s', \
        datefmt='%H:%M:%S', \
        handlers=[logging.FileHandler("codec2-FreeDATA-TNC.log"),logging.StreamHandler()]
        )

    logging.addLevelName(logging.DEBUG, "\033[1;36m%s\033[1;0m" % logging.getLevelName(logging.DEBUG))
    logging.addLevelName(logging.INFO, "\033[1;37m%s\033[1;0m" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, "\033[1;31m%s\033[1;0m" % "FAILED")
    #logging.addLevelName( logging.ERROR, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))
    logging.addLevelName(logging.CRITICAL, "\033[1;41m%s\033[1;0m" % logging.getLevelName(logging.CRITICAL))

    logging.addLevelName(25, "\033[1;32m%s\033[1;0m" % "SUCCESS")
    logging.addLevelName(24, "\033[1;34m%s\033[1;0m" % "DATA")


