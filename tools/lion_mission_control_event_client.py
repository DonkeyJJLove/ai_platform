#!/usr/bin/env python3
import argparse,json,socket
from cyber_lion.mission_control.schema import validate_event
def main():
 p=argparse.ArgumentParser();p.add_argument('event_json');p.add_argument('--socket',default='/run/lion-mission-control/events.sock');a=p.parse_args();e=validate_event(json.loads(a.event_json));s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect(a.socket);s.sendall(json.dumps(e,separators=(',',':')).encode());s.close()
if __name__=='__main__':main()
