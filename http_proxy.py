import socket
import threading

class HTTPProxy:
    """
    HTTP代理服务器实现
    
    注意：这个实现只处理HTTP请求，不处理HTTPS请求
    
    HTTP代理请求格式说明：
    1. 直接访问服务器时的请求格式：
       GET /index.html HTTP/1.1
       Host: www.example.com
    
    2. 通过代理访问时的请求格式：
       GET http://www.example.com/index.html HTTP/1.1
       Host: www.example.com
    
    因此代理服务器需要：
    1. 解析完整URL获取目标服务器信息
    2. 将代理格式请求转换为直接访问格式
    3. 转发修改后的请求到目标服务器
    """
    def __init__(self, host='127.0.0.1', port=8080):
        self.host = host
        self.port = port

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        print(f"HTTP 代理服务器运行在 {self.host}:{self.port}")

        while True:
            try:
                client_socket, client_addr = server.accept()
                thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                thread.start()
            except Exception as e:
                print(f"接受连接时出错: {e}")

    def handle_client(self, client_socket):
        try:
            request = client_socket.recv(8192)
            if not request:
                return

            # 解析HTTP请求
            first_line = request.decode('utf-8').split('\r\n')[0]
            method, full_path, version = first_line.split(' ')

            # 处理普通HTTP请求
            if not full_path.startswith('http'):
                client_socket.close()
                return
            
            # 移除 http://
            path = full_path.split('://', 1)[1]
            hostname = path.split('/')[0]
            port = 80
            
            if ':' in hostname:
                hostname, port = hostname.split(':')
                port = int(port)

            # 连接目标服务器
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.connect((hostname, port))

            # 转发修改后的请求
            modified_request = self.modify_request(request, hostname)
            server_socket.send(modified_request)

            # 开始双向转发数据
            self.forward_data(client_socket, server_socket)

        except Exception as e:
            print(f"处理客户端请求时出错: {e}")
        finally:
            client_socket.close()

    def modify_request(self, request, hostname):
        # 修改HTTP请求，移除完整URL，只保留路径部分
        lines = request.decode('utf-8').split('\r\n')
        method, full_path, version = lines[0].split(' ')
        path = '/' + full_path.split('://', 1)[1].split('/', 1)[1] if '/' in full_path else '/'
        lines[0] = f"{method} {path} {version}"
        
        # 确保Host头部正确
        has_host = False
        for i, line in enumerate(lines[1:], 1):
            if line.lower().startswith('host:'):
                lines[i] = f"Host: {hostname}"
                has_host = True
                break
        
        if not has_host:
            lines.insert(1, f"Host: {hostname}")
        
        return '\r\n'.join(lines).encode('utf-8')

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
    proxy = HTTPProxy()
    proxy.start()
