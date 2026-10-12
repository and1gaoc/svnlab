# SVNLab

SVNLab 是一个本地运行、只读的 Subversion 提交浏览器。它用类似 GitLab 的界面展示提交历史，并在一个页面中自动展示某次提交涉及的所有文件和完整 diff。

## 功能

- 通过仓库地址、SVN 用户名和密码连接 `file://`、`svn://` 或 HTTP(S) 仓库。
- 按时间浏览提交记录并按版本号跳转。
- 在一个页面内自动展示一次提交的全部文件和全部 diff。
- 在并排与单栏 diff 间切换；窄屏使用单栏布局。
- 使用吸附式文件目录快速定位长提交中的文件。
- 按需向上、向下或双向展开未变更的上下文代码。
- 分段查看文件在当前版本中的内容。
- 识别新增、删除、替换、二进制和仅属性变化。
- 后端不保存凭据，不缓存 SVN 认证信息，也不提供任何仓库写操作。

## 前置要求

- Python 3.11 或更高版本。
- 官方 Subversion 命令行客户端，`svn` 必须可从 `PATH` 执行。
- 推荐安装 [uv](https://docs.astral.sh/uv/)，也可以使用普通 `venv` 和 `pip`。

确认 SVN CLI：

```powershell
svn --version --quiet
```

Windows 可安装 VisualSVN、SlikSVN 或其他包含命令行客户端的 Subversion 发行版。Linux 通常可以从系统包管理器安装 `subversion`。

## 安装与启动

使用 uv：

```powershell
uv sync
uv run svnlab
```

使用 venv 和 pip：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m svnlab
```

启动后访问 <http://127.0.0.1:8000>。

服务默认只监听本机回环地址。API 文档位于 <http://127.0.0.1:8000/api/docs>。

## 使用方式

1. 打开 SVNLab，填写仓库地址、用户名和密码。
2. 点击“测试连接并进入”。连接成功后，设置会保存到当前浏览器的 `localStorage`。
3. 在提交记录中选择版本，详情页会自动显示本次提交的全部 diff。
4. 使用顶部“并排 / 单栏”切换所有文件的显示模式。
5. 在隐藏上下文区域点击 `↑`、`↕` 或 `↓`，每次补充读取 20 行。
6. 点击文件标题中的“查看文件”，按 200 行一段浏览当前版本内容。

## 凭据与安全边界

- SVNLab 没有应用登录功能，定位为可信电脑上的本地工具。
- 仓库地址、用户名和密码保存在浏览器 `localStorage`；能访问该浏览器配置的人也可以读取密码。
- 凭据会随同源 POST 请求发送给本机后端，不会进入 URL，也不会由后端写入文件或应用日志。
- 后端使用 `--non-interactive --no-auth-cache` 调用 SVN，不会写入 SVN 的认证缓存。
- 采用 CLI 集成时，密码可能在 SVN 子进程存活期间短暂出现在本机进程参数中。
- 应用不会自动信任无效 TLS 证书。请先用本机 SVN 客户端确认并保存证书信任设置。
- 不要把本应用直接暴露到公网。

## 开发与测试

```powershell
uv sync --extra dev
uv run pytest
```

测试套件包含模型校验、SVN XML/diff 解析、命令安全、缓存和 API 测试。如果系统同时安装了 `svn` 与 `svnadmin`，还会创建临时本地仓库并运行真实集成测试；缺少这些命令时，该项测试会明确跳过。

## 项目结构

```text
svnlab/
  api.py          FastAPI 路由
  app.py          应用装配与静态资源服务
  cache.py        有界文件内容缓存
  models.py       请求、提交和 diff 数据模型
  parsers.py      SVN XML 与 unified diff 解析
  svn_client.py   安全的 SVN 子进程适配器
  static/         原生 HTML、CSS、JavaScript 前端
tests/            自动化测试
```

## 当前范围

SVNLab 是只读浏览器，不包含用户系统、仓库写入、代码评论、问题跟踪、合并请求或 CI/CD。

