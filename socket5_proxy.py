import socket
import threading
import struct

class SOCKS5Proxy:
    def __init__(self, host='127.0.0.1', port=1080):
        self.host = host
        self.port = port

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        print(f"SOCKS5 代理服务器运行在 {self.host}:{self.port}")

        while True:
            try:
                client_socket, client_addr = server.accept()
                thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                thread.start()
            except Exception as e:
                print(f"接受连接时出错: {e}")

    def handle_client(self, client_socket):
        try:
            # SOCKS5 认证协商
            if not self.handle_auth(client_socket):
                return

            # SOCKS5 请求处理
            if not self.handle_request(client_socket):
                return

        except Exception as e:
            print(f"处理客户端请求时出错: {e}")
        finally:
            client_socket.close()

    def handle_auth(self, client_socket):
        # 接收客户端支持的认证方法
        version, nmethods = struct.unpack('!BB', client_socket.recv(2))
        methods = client_socket.recv(nmethods)

        # 目前仅支持无认证方式(0x00)
        client_socket.send(struct.pack('!BB', 0x05, 0x00))
        return True

    def handle_request(self, client_socket):
        # 接收请求详情
        version, cmd, _, addr_type = struct.unpack('!BBBB', client_socket.recv(4))
        
        if cmd != 0x01:  # 仅支持 CONNECT 命令
            self.send_reply(client_socket, 0x07)  # Command not supported
            return False

        # 解析目标地址
        if addr_type == 0x01:  # IPv4
            target_addr = socket.inet_ntoa(client_socket.recv(4))
        elif addr_type == 0x03:  # Domain name
            addr_len = ord(client_socket.recv(1))
            target_addr = client_socket.recv(addr_len).decode('utf-8')
        elif addr_type == 0x04:  # IPv6
            target_addr = socket.inet_ntop(socket.AF_INET6, client_socket.recv(16))
        else:
            self.send_reply(client_socket, 0x08)  # Address type not supported
            return False

        # 获取端口号
        target_port = struct.unpack('!H', client_socket.recv(2))[0]

        try:
            # 连接目标服务器
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.connect((target_addr, target_port))
            bind_addr = server_socket.getsockname()
            
            # 发送成功响应
            self.send_reply(client_socket, 0x00, bind_addr[0], bind_addr[1])
            
            # 开始转发数据
            self.forward_data(client_socket, server_socket)
            return True

        except Exception as e:
            print(f"连接目标服务器失败: {e}")
            self.send_reply(client_socket, 0x04)  # Host unreachable
            return False

    def send_reply(self, client_socket, reply_code, bind_addr='0.0.0.0', bind_port=0):
        # 构造响应包
        response = struct.pack('!BBBB', 0x05, reply_code, 0x00, 0x01)
        response += socket.inet_aton(bind_addr)
        response += struct.pack('!H', bind_port)
        client_socket.send(response)

    def forward_data(self, client_socket, server_socket):
        def forward(source, destination, description):
            try:
                while True:
                    data = source.recv(8192)
                    if not data:
                        break
                    destination.send(data)
            except:
                pass
            finally:
                try:
                    source.close()
                    destination.close()
                except:
                    pass

        threading.Thread(target=forward, args=(client_socket, server_socket, "客户端 -> 服务器")).start()
        threading.Thread(target=forward, args=(server_socket, client_socket, "服务器 -> 客户端")).start()

if __name__ == '__main__':
    proxy = SOCKS5Proxy()
    proxy.start()
