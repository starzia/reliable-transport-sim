from socket import socket, AF_INET, SOCK_DGRAM
import random
from threading import Timer
from time import sleep
from typing import Tuple

# constant seed makes the random number generator deterministic during testing
random.seed(398120)


class SimulationParams:
    def __init__(self, loss_rate: float=0.0, corruption_rate: float=0.0,
                 max_delivery_delay: float=0.0):
        self.loss_rate = loss_rate
        self.corruption_rate = corruption_rate
        self.max_delivery_delay = max_delivery_delay

# global simulation parameters
sim = SimulationParams()


class LossyUDP(socket):
    def __init__(self):
        self.packets_sent = 0
        self.packets_recv = 0
        self.bytes_sent = 0
        self.bytes_recv = 0
        super().__init__(AF_INET, SOCK_DGRAM)

    def __del__(self):
        # for our purposes, we always want to unbind the port when the app stops
        super().close()
        # print some stats
        print("PACKETS_SENT=%d" % self.packets_sent)
        print("PACKETS_RECV=%d" % self.packets_recv)
        print("BYTES_SENT=%d" % self.bytes_sent)
        print("BYTES_RECV=%d" % self.bytes_recv)

    def sendto(self, message: bytes, dst: Tuple[str, int]):
        """Unlike the sendto method provided by the BSD socket lib,
           this method never blocks (because it schedules the transmission on a thread)."""
        if len(message) > 1472:
            raise RuntimeError("You are trying to send more than 1472 bytes in one UDP packet!")
        self.packets_sent += 1
        self.bytes_sent += len(message)
        # sleep() spaces out the requests enough to eliminate reordering caused by the OS process/thread scheduler.
        # It also limits the peak throughput of the socket :(
        sleep(0.01)
        if random.random() < sim.loss_rate:
            # drop the packet
            print("outgoing UDP packet was dropped by the simulator.")
        elif random.random() < sim.corruption_rate:
            # corrupt the packet
            bit_to_flip = random.randint(0, len(message) * 8 - 1)
            byte_to_be_flipped = message[int(bit_to_flip / 8)]
            flipped_byte = byte_to_be_flipped ^ (1 << (bit_to_flip % 8))
            # bytes type is not mutable, but bytearray is:
            msg_array = bytearray(message)
            msg_array[int(bit_to_flip / 8)] = flipped_byte
            message = bytes(msg_array)
            print("outgoing UDP packet's bit number %d was flipped by the simulator."
                  % bit_to_flip)
        else:
            # send message after a random delay.  The randomness will reorder packets
            Timer(random.random() * sim.max_delivery_delay,
                  lambda: super(self.__class__, self).sendto(message, dst)).start()

    def recvfrom(self, bufsize: int=2048) -> (bytes, (str, int)):
        """Blocks until a packet is received.
           returns (data, (source_ip, source_port))"""
        while True:
            try:
                data, addr = super().recvfrom(bufsize)
                self.packets_recv += 1
                self.bytes_recv += len(data)
            except InterruptedError:
                # note that on Python >= 3.5, this exception will not happen:
                # https://www.python.org/dev/peps/pep-0475/
                continue
            else:
                return data, addr
