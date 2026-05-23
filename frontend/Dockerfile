# 新前端是 v0.dev 静态原型：CDN 加载 React + 浏览器内 Babel 编译 v0/*.jsx。
# 无构建步骤，直接用 nginx 托管静态文件即可。
FROM nginx:alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY AgentHub-v0.html /usr/share/nginx/html/AgentHub-v0.html
COPY v0/ /usr/share/nginx/html/v0/

EXPOSE 80
