import socket
c = socket.socket()
c.connect(('192.168.1.40', 1883))
c.sendall(b'\x10\x12\x00\x04MQTT\x04\x02\x00<\x00\x06py_stp')
c.recv(4)
payload = b'{"cmd":"stop"}'
cmd_body = b'\x00\x0fcontrol/motores' + payload
c.sendall(bytes([0x30, len(cmd_body)]) + cmd_body)
print('Comando STOP enviado!')
c.close()
