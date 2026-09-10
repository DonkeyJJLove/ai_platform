#!/usr/bin/env python3
import argparse,json,socket
from cyber_lion.mission_control.schema import validate_event
def main():
 p=argparse.ArgumentParser();sp=p.add_subparsers(dest='command',required=True);e=sp.add_parser('emit');e.add_argument('event_json');e.add_argument('--socket',default='/run/lion-mission-control/events.sock');a=p.parse_args();event=validate_event(json.loads(a.event_json));s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect(a.socket);s.sendall(json.dumps(event,separators=(',',':')).encode());s.close()
if __name__=='__main__':main()
