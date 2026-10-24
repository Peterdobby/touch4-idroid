#!/usr/bin/env python3
"""List or test Linux ACM (0525:a4a7), after manual RAM boot. No DFU or storage."""
import argparse,glob,os,select,sys,termios,time,fcntl,struct

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--list',action='store_true');p.add_argument('--port');p.add_argument('--seconds',type=float,default=15)
    a=p.parse_args();ports=sorted(glob.glob('/dev/cu.usbmodem*'))
    if a.list:
        print('\n'.join(ports) if ports else 'No /dev/cu.usbmodem* ports found.');return 0
    port=a.port
    if not port:
        if len(ports)!=1:p.error('Specify --port; found: '+repr(ports))
        port=ports[0]
    if not port.startswith('/dev/cu.usbmodem') or port not in ports:p.error('Port must be a detected /dev/cu.usbmodem* device')
    fd=os.open(port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
    old=termios.tcgetattr(fd)
    try:
        t=termios.tcgetattr(fd);t[0]=t[1]=t[3]=0;t[2]=termios.CS8|termios.CREAD|termios.CLOCAL;t[4]=t[5]=termios.B115200;t[6][termios.VMIN]=0;t[6][termios.VTIME]=0
        termios.tcsetattr(fd,termios.TCSANOW,t)
        if hasattr(termios,'TIOCMBIS'):fcntl.ioctl(fd,termios.TIOCMBIS,struct.pack('I',termios.TIOCM_DTR|termios.TIOCM_RTS))
        print('ACM opened:',port,flush=True)
        token=b'T4_HOST_ECHO_CHECK\n';seen=b'';until=time.monotonic()+a.seconds;sent=False
        while time.monotonic()<until:
            if not sent:
                try:sent=os.write(fd,token)==len(token)
                except BlockingIOError:pass
            if select.select([fd],[],[],0.2)[0]:
                try:b=os.read(fd,4096)
                except BlockingIOError:continue
                if b:sys.stdout.buffer.write(b);sys.stdout.buffer.flush();seen+=b
        alive=b'T4_USB_ACM_01 RAM serial alive' in seen
        echo=b'T4_HOST_ECHO_CHECK' in seen
        print('\nRAM_HEARTBEAT='+str(alive)+' HOST_ECHO='+str(echo))
        return 0 if alive and echo else 2
    finally:
        try:termios.tcsetattr(fd,termios.TCSANOW,old)
        finally:os.close(fd)
if __name__=='__main__':raise SystemExit(main())
