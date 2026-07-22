# 本地运行说明

这个项目不需要 WMI/Win32 启动。之前使用 WMI 只是为了绕过 Codex 沙箱里的后台进程限制，正常分发给别人时请使用下面的脚本。

## 推荐运行方式：前台窗口

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-foreground.ps1
```

这会打开两个普通 PowerShell 窗口：一个后端、一个前端。关闭这两个窗口即可停止服务，进程透明，不使用 WMI/Win32 后台创建。

脚本会把所有项目运行文件放在项目目录内：

- Python 虚拟环境：`.venv/`
- 前端依赖：`frontend/node_modules/`
- 运行日志和进程号：`runtime/`
- SQLite 数据库：`backend/data/app.db`

不会把项目运行文件写到 C 盘。Python、Node.js 本身如果安装在 C 盘，那是开发环境安装位置，不是项目运行产物。

## 再次运行

依赖已经安装过时可以跳过安装：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-foreground.ps1 -SkipInstall
```

访问地址：

- 前端：http://127.0.0.1:5173/
- 后端：http://127.0.0.1:8000/api/health

## 停止服务

前台模式下，直接关闭脚本打开的两个 PowerShell 窗口即可。

如果使用后台模式 `scripts\start.ps1`，再用下面命令停止：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
```

后台模式会使用 PowerShell `Start-Process` 创建隐藏进程并写入 `runtime/pids.json`。推荐给别人演示时优先使用前台模式，因为更直观，哪里在占内存一眼就能看到。

## 发送给别人前

不要包含这些目录或文件：

- `.venv/`
- `frontend/node_modules/`
- `frontend/dist/`
- `runtime/`
- `.env`
- `backend/data/*.db`

可以提供 `.env.example`，让对方自己填写 API Key。
