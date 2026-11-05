import socket
c = socket.socket()
c.connect(('192.168.1.40', 1883))
c.sendall(b'\x10\x12\x00\x04MQTT\x04\x02\x00<\x00\x06py_cli')
resp = c.recv(4)
print('Connack:', resp)
# Topic: control/motores (15 bytes), payload: {"cmd":"test"} (14 bytes)
# Total length = 2 + 15 + 14 = 31 = 0x1f
body = b'\x00\x0fcontrol/motores{"cmd":"test"}'
c.sendall(bytes([0x30, len(body)]) + body)
print('Publicado exitosamente!')
c.close()
