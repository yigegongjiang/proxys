import socket
import threading

class ProxyServer:
    def __init__(self, host='127.0.0.1', port=8443):  # 修改默认 host 为 127.0.0.1
        self.host = host
        self.port = port

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        print(f"HTTPS 代理服务器运行在 {self.host}:{self.port}")

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
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.settimeout(10)  # 添加超时设置
                server_socket.connect((hostname, port))
                client_socket.send(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                self.forward_data(client_socket, server_socket)
            except socket.timeout:
                print(f"连接 {hostname}:{port} 超时")
            except ConnectionRefusedError:
                print(f"连接 {hostname}:{port} 被拒绝")
            except Exception as e:
                print(f"连接目标服务器时出错: {e}")

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
                    destination.send(data)
            except (ConnectionResetError, BrokenPipeError) as e:
                print(f"{description} 连接断开: {e}")
            except Exception as e:
                print(f"{description} 转发错误: {e}")
            finally:
                try:
                    source.close()
                    destination.close()
                except:
                    pass

        client_to_server = threading.Thread(
            target=forward, 
            args=(client_socket, server_socket, "客户端到服务器")
        )
        server_to_client = threading.Thread(
            target=forward, 
            args=(server_socket, client_socket, "服务器到客户端")
        )

        client_to_server.start()
        server_to_client.start()

if __name__ == '__main__':
    proxy = ProxyServer()
    proxy.start()
