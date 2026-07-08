# public-opinion-analysis
网络舆情事件智能分析系统


## API接口文档

### 1. 登录
POST /api/login
请求：{"username":"admin","password":"123456"}
返回：{"code":0,"message":"登录成功","data":{"token":"xxx"}}

### 2. 事件列表
GET /api/events?sort=heat
返回：{"code":0,"data":[{"id":1,"title":"xxx","heat":95,"sentiment":{"positive":10,"negative":65,"neutral":25}}]}

### 3. 事件详情
GET /api/events/:id
返回：{"code":0,"data":{"id":1,"title":"xxx","summary":"xxx","sentiment":{},"platforms":{},"keywords":[],"trend":[]}}

### 4. 个人中心
GET /api/profile  获取配置
POST /api/profile 保存配置
请求：{"platforms":["url"],"keywords":["关键词"]}
返回：{"code":0,"data":{"platforms":[],"keywords":[]}}
