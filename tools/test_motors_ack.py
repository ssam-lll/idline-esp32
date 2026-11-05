import socket
c = socket.socket()
c.connect(('192.168.1.40', 1883))
c.sendall(b'\x10\x12\x00\x04MQTT\x04\x02\x00<\x00\x06py_sub2')
c.recv(4)
body = b'\x00\x01\x00\x18telemetria/motores/estado\x00'
c.sendall(bytes([0x82, len(body)]) + body)
c.recv(5)

# Now send test command
body2 = b'\x00\x0fcontrol/motores{"cmd":"test"}'
c.sendall(bytes([0x30, len(body2)]) + body2)

c.settimeout(2.5)
try:
    while True:
        data = c.recv(1024)
        if data:
            print('ACK / Estado msg:', data)
except Exception:
    pass
c.close()
