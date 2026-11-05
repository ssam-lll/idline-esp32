import socket
c = socket.socket()
c.connect(('192.168.1.40', 1883))
c.sendall(b'\x10\x12\x00\x04MQTT\x04\x02\x00<\x00\x06py_inj')
c.recv(4)

sub_body = b'\x00\x01\x00\x13telemetria/sensores\x00'
c.sendall(bytes([0x82, len(sub_body)]) + sub_body)
c.recv(5)

# Topic: control/motores (15 bytes), payload: {"cmd":"set_motores","m1":200,"m2":200}
payload = b'{"cmd":"set_motores","m1":200,"m2":200}'
cmd_body = b'\x00\x0fcontrol/motores' + payload
c.sendall(bytes([0x30, len(cmd_body)]) + cmd_body)
print('Comando set_motores enviado!')

c.settimeout(2.5)
try:
    for _ in range(4):
        d = c.recv(1024)
        idx = d.find(b'{')
        if idx != -1:
            print('RESP:', d[idx:].decode('utf-8', errors='ignore'))
except Exception as e:
    print('Terminado:', e)
c.close()
