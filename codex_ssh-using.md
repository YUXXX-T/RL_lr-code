## codex cli安装
```
npm install -g @openai/codex
# 如果比较慢可以使用镜像站
npm i -g @openai/codex --registry=https://registry.npmmirror.com

# 验证
codex --version
```

## nomachine连接
windows 下打开终端，设置ssh转发
```
ssh -N -L 4040:127.0.0.1:4040 用户名@ip -p 端口号
```
运行后不关闭终端，保持终端在后台持续运行
在nomachine中设置 Host为127.0.0.1 Port为4040 默认连接协议为NX即可连接

## 安装与配置 mihomo

```
mkdir -p ~/mihomo-cli && cd ~/mihomo-cli
wget https://github.com/MetaCubeX/mihomo/releases/download/v1.18.3/mihomo-linux-amd64-v1.18.3.gz
gzip -d mihomo-linux-amd64-v1.18.3.gz

# 重命名并赋予执行权限
mv mihomo-linux-amd64-v1.18.3 mihomo

# 伪装成 Clash 客户端 获取订阅配置
wget -O config.yaml -U "clash-meta" "vpn订阅链接"
# 检查获取配置
head -n 10 config.yaml

# 启动核心
cd ~/mihomo-cli
./mihomo -d .
```
看见 "Start initial Compatible provider" 即成功

## 修改代理节点
在本地 windows 下新建终端，设置ssh转发
```
ssh -N -L 9090:127.0.0.1:9090 用户名@ip -p 端口号
```

打开下方链接网页，进入控制 Clash 核心：
http://metacubex.github.io/metacubexd/

打开网页后，会提示需要连接后台，Host填入127.0.0.1，Port填入9090。
进入后即可选择节点

## 使用代理

完成上述步骤后，在 vscode 内新建ssh终端
声明环境变量（mihomo 默认提供的 HTTP 代理端口是 7890）：
```
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"

codex
```

## 注意事项
如果挂代理并且想要通过nomachine连接，需要两个不同端口的ssh转发(e.g., 4040 and 9090)，不能用在同一个！！！


# 构建 Dockerfile
开了 vpn 之后
```
mkdir -p /etc/systemd/system/docker.service.d
```

直接复制以下这段：
```
tee /etc/systemd/system/docker.service.d/http-proxy.conf <<-'EOF'
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1,docker-registry.somecorporation.com"
EOF
```

重新载入系统设定并重启 dokcer
```
systemctl daemon-reload
systemctl restart docker
```

绑上代理后重新 构建
```
docker build --network host --build-arg HTTP_PROXY=http://127.0.0.1:7890 --build-arg HTTPS_PROXY=http://127.0.0.1:7890 -t first_airesearcher:v1 .
```

构建完后，删除
```
rm -f /etc/systemd/system/docker.service.d/http-proxy.conf
systemctl daemon-reload
systemctl restart docker
```
