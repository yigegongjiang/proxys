import socket
import ssl
import threading
from OpenSSL import crypto
import os

class CertificateAuthority:
    def __init__(self):
        self.ca_cert_path = 'ca.crt'
        self.ca_key_path = 'ca.key'
        self.create_ca_cert()

    def create_ca_cert(self):
        if os.path.exists(self.ca_cert_path) and os.path.exists(self.ca_key_path):
            return

        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 2048)

        cert = crypto.X509()
        cert.get_subject().CN = "MITM Proxy CA"
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(315360000)  # 10年有效期
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.sign(key, 'sha256')

        with open(self.ca_cert_path, 'wb') as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(self.ca_key_path, 'wb') as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

    def generate_cert(self, hostname):
        with open(self.ca_cert_path, 'rb') as f:
            ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, f.read())
        with open(self.ca_key_path, 'rb') as f:
            ca_key = crypto.load_privatekey(crypto.FILETYPE_PEM, f.read())

        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 2048)

        cert = crypto.X509()
        cert.get_subject().CN = hostname
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(31536000)  # 1年有效期
        cert.set_issuer(ca_cert.get_subject())
        cert.set_pubkey(key)
        cert.sign(ca_key, 'sha256')

        cert_path = f'certs/{hostname}.crt'
        key_path = f'certs/{hostname}.key'

        os.makedirs('certs', exist_ok=True)
        
        with open(cert_path, 'wb') as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(key_path, 'wb') as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

        return cert_path, key_path

class MITMProxy:
    def __init__(self, host='127.0.0.1', port=8443):
        self.host = host
        self.port = port
        self.ca = CertificateAuthority()

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        print(f"MITM 代理服务器运行在 {self.host}:{self.port}")

        while True:
            try:
                client_socket, client_addr = server.accept()
                thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                thread.start()
            except Exception as e:
                print(f"接受连接时出错: {e}")

    def handle_client(self, client_socket):
        try:
            data = client_socket.recv(8192)
            if not data:
                return

            first_line = data.decode('utf-8').split('\r\n')[0]
            method, target_host, _ = first_line.split(' ')

            if method != 'CONNECT':
                client_socket.close()
                return

            hostname = target_host.split(':')[0]
            port = int(target_host.split(':')[1]) if ':' in target_host else 443

            try:
                # 生成域名证书
                cert_path, key_path = self.ca.generate_cert(hostname)

                # 连接目标服务器
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.settimeout(10)
                server_socket.connect((hostname, port))
                
                # 与目标服务器建立 SSL 连接
                context = ssl.create_default_context()
                ssl_server = context.wrap_socket(
                    server_socket, 
                    server_hostname=hostname
                )

                # 告诉客户端隧道已建立
                client_socket.send(b'HTTP/1.1 200 Connection Established\r\n\r\n')

                # 与客户端建立 SSL 连接
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                context.load_cert_chain(cert_path, key_path)
                ssl_client = context.wrap_socket(
                    client_socket,
                    server_side=True
                )

                self.forward_data(ssl_client, ssl_server)

            except Exception as e:
                print(f"处理 HTTPS 连接时出错: {e}")

        except Exception as e:
            print(f"处理客户端请求时出错: {e}")
        finally:
            client_socket.close()

    def forward_data(self, client_socket, server_socket):
        def forward(source, destination, description):
            try:
                while True:
                    data = source.recv(8192)
                    if not data:
                        break
                    print(f"\n{description} 数据:")
                    try:
                        print(data.decode('utf-8'))
                    except:
                        print("[二进制数据]")
                    destination.send(data)
            except Exception as e:
                print(f"{description} 错误: {e}")
            finally:
                try:
                    source.close()
                    destination.close()
                except:
                    pass

        client_to_server = threading.Thread(
            target=forward, 
            args=(client_socket, server_socket, "客户端 -> 服务器")
        )
        server_to_client = threading.Thread(
            target=forward, 
            args=(server_socket, client_socket, "服务器 -> 客户端")
        )

        client_to_server.start()
        server_to_client.start()

if __name__ == '__main__':
    proxy = MITMProxy()
    proxy.start()
