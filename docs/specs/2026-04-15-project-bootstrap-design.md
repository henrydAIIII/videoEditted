# 视频合成工具初始化设计

## 目标

在现有素材仓库基础上初始化一个可运行的前后端工程骨架，满足毕业设计演示项目的技术约束，并为后续 `timeline.json -> 合成视频` 核心渲染管线提供清晰的模块边界。

## 范围

- 创建 `frontend` React + Tailwind 项目骨架
- 创建 `backend` FastAPI 项目骨架
- 统一后端返回格式为 `{code, data, message}`
- 预留 `timeline` 解析、场景渲染、图层叠加、字幕和音频混合模块
- 提供示例 `timeline.json`、环境变量样例和 README
- 安装前后端基础依赖并验证可启动

## 不在本次范围

- 不实现真实视频渲染逻辑
- 不接入真实大模型调用
- 不完成完整时间轴编辑交互

## 目录设计

- `frontend/src/pages` 放页面入口
- `frontend/src/components` 放时间轴和预览组件
- `frontend/src/lib` 放 API 客户端和常量
- `backend/app/api` 放路由
- `backend/app/core` 放配置和统一响应
- `backend/app/schemas` 放 Pydantic 数据结构
- `backend/app/services` 放渲染相关服务
- `backend/app/models` 放时间轴领域模型
- `backend/tests` 放后端测试

## 初始化策略

- 前端使用 Vite，保留最小页面与 Tailwind 样式入口
- 后端使用 Python 虚拟环境 + `requirements.txt`
- 先写一个后端测试，约束健康检查接口返回格式
- 通过占位实现让测试通过，确保后续扩展不偏离接口约定
