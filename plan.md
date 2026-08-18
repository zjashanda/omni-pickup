# 任务计划

## 目标
- 阅读 `Z:\revolution4s\xmosRecord` 目录下的所有文件。

## 状态
- [x] 读取并确认当前目录原有 `plan.md`：不存在，已创建。
- [x] 盘点目标目录及文件清单：共 27 个文件，包含文本、Python、构建产物、图像、可执行文件和约 2.7 GB PCM 音频。
- [x] 读取所有可读文本文件并记录关键信息：Python 源码、启动脚本、spec、PyInstaller TOC、警告文件和 6708 行 XRef。
- [x] 识别二进制/超大文件并完成检查：图片/ICO 尺寸与条目、EXE PE 头、PYZ/ZIP 清单、PYC 代码元数据、Thumbs.db 头部；`tes3.pcm` 分块读完整体并计算 SHA-256。
- [x] 汇总已执行、未执行和待执行事项，更新本计划。

## 已完成读取摘要
- 文件总数：27；目录数：7；总大小约 2.595 GiB。
- 主程序：`record_asio_pcm.py`，基于 PyAudio/PortAudio 的 ASIO 原始 PCM 录音器；默认 48 kHz、8 通道、16 bit、4800 frames/buffer，支持设备选择、格式校验、定时/持续录音、设备断开检测和进度输出。
- 入口脚本：`.cmd` 与 `.ps1` 都转发参数到 Python 源码；PyInstaller spec 生成控制台单文件 EXE，并使用 `assets\record_asio_pcm.ico`。
- 构建：两个 EXE（根目录与 `dist`）字节一致，PE32+ x64，时间戳 2026-03-25 13:59:29；PYZ 含 87 个模块，base_library.zip 含 152 个条目；警告仅为可选/跨平台模块缺失。
- 图像：`graphic_eq_source.png` 为 96x96 白色均衡器图标；`record_asio_pcm_icon.png` 为 512x512 深色圆角图标；ICO 含 16/24/32/48/64/128/256 共 7 个 32 位尺寸。
- 音频：`tes3.pcm` 为 2,764,800,000 字节，按 48 kHz × 8 × 16 bit 推断正好 3600 秒（1 小时），首/中/尾分段均为有效的有符号 16 位多通道数据；SHA-256 `424e987bc44daccfd4a3b074a1ff86ba9868d506581d629cd03c9d881839bb31`。
- 启动验证：打包 EXE 的 `--help` 成功；当前 Python 3.9 直接运行源码因环境缺少 `pyaudio` 而失败。未执行实际录音或声卡探测。

## 未执行/待执行
- 未执行实际 ASIO 录音、`--list-devices` 或 `--validate-only`，因为这会依赖当前机器的声卡/驱动，且用户当前只要求阅读文件。

## 当前追加任务
- [x] 细读 `Z:\revolution4s\xmosRecord\record_asio_pcm.py`，说明用途、参数、录音流程和运行前提。

### 主程序细读结论
- 程序用途：通过 PyAudio/PortAudio 打开 ASIO 输入设备，按指定采样率、通道数和位深持续读取音频帧，并写成无文件头的交错原始 PCM 文件。
- 默认配置：设备名 `iFlyRec USB Audio ASIO Driver`、ASIO 主机 API、48 kHz、8 通道、16 bit、每次读取 4800 frames。
- 设备流程：只筛选 ASIO 且有输入通道的设备；设备名支持标准化后的精确匹配或子串匹配，也可按设备索引；随后校验输入通道数和 PortAudio 格式支持情况。
- 录音流程：按固定时长或持续模式读取；每秒刷新进度并每秒检查设备是否仍存在；流异常、设备断开、Ctrl+C 都有对应清理和退出处理。
- 输出行为：指定 `-o/--output/--name` 时使用给定路径，否则在 `--output-dir` 下生成 `YYYYMMDD_HHMMSS.pcm`；不会写 WAV 头，因此回放/解析必须知道 PCM 参数。
- 运行前提：源码需要可导入的 `pyaudio` 和可见的 ASIO 驱动；打包 EXE 已内置相关运行库。`--list-devices` 只列出设备，`--validate-only` 只做设备/格式校验。

## 重写脚本追加任务
- [x] 在当前目录创建兼容多 Host API 的新录音脚本，不改动原脚本：`recorderByDWWM.py`。
- [x] 保留原有录音参数、输出格式、持续/定时录音、进度、断开检测和清理逻辑。
- [x] 增加 ASIO、DirectSound、WASAPI、WDM-KS 的 Host API 选择和设备过滤；默认 Host API 改为 WASAPI。
- [x] `--list-devices` 按 ASIO、DirectSound、WASAPI、WDM-KS、Other 分组，同组使用 `--<索引>` 下一行缩进显示设备名，并显示通道/默认采样率。
- [x] 进行 `--help`、静态语法、参数错误和无 PyAudio 环境下的受控失败验证；用假的 PortAudio 后端完成分组、默认选择和固定时长写 PCM smoke。
- [x] 将实现、限制和验证结果回写本计划。

### 帮助参数验证
- [x] `recorderByDWWM.py -h`、`record_audio_pcm.cmd -h`、`record_audio_pcm.ps1 -h` 均成功输出 `usage`；`argparse` 自动提供 `-h/--help`。

### 文件重命名
- [x] 将当前新录音脚本最终命名为 `OmniPickup.py`，并同步更新 `OmniPickup.cmd`、`OmniPickup.ps1`、`OmniPickup.spec`；原 `record_asio_pcm.py` 保持不变。

### 新脚本限制
- 录音只选择具有输入通道的设备；设备列表中的 `outputs` 仅用于识别端点能力，不会把普通扬声器输出端点当成输入录音源。
- WASAPI 系统播放回录（loopback）需要专门的 WASAPI loopback 支持，本脚本当前保持与原脚本一致的输入采集模式。
- 当前环境没有安装 `pyaudio`，所以未连接真实声卡；安装支持目标 Host API 的 PyAudio/PortAudio 后才能执行真实 `--list-devices`、校验和录音。

### 当前运行阻塞
- [x] 已确认系统 `python` 为 Python 3.14，系统环境未安装 PyAudio；原阻塞已隔离处理。
- [x] 在当前目录创建独立虚拟环境 `.venv`，解释器为 Python 3.10.11，安装 `PyAudio==0.2.14`，未修改系统环境。
- [x] 使用 `.venv` 实际枚举 58 个设备；标准 wheel 提供 MME、DirectSound、WASAPI、WDM-KS，未提供 ASIO Host API。
- [x] 使用 WASAPI 设备索引 32 以 16 kHz、8 通道、16 bit 执行 `--validate-only`，校验通过。
- [ ] 若需要 ASIO，安装/构建带 ASIO 支持的 PortAudio/PyAudio，并重新验证 ASIO 设备。

## EXE 打包追加任务
- [x] 在 `.venv` 内安装 PyInstaller 6.22.2。
- [x] 将 `recorderByDWWM.py` 打包为独立单文件 `dist_recorderByDWWM\recorderByDWWM.exe`，使用 `build_recorderByDWWM` / `dist_recorderByDWWM` 专用目录，并嵌入 `record_asio_pcm.ico` 图标。
- [x] 验证 EXE 的帮助、设备枚举和 WASAPI 格式校验；EXE 为 6,539,296 字节，直接启动成功，不调用 `.venv` Python。

## 名称调整追加任务
- [x] 将用户-facing 录音脚本名称调整为 `OmniPickup`，同步入口、spec 和打包名称；新 EXE 位于 `dist_OmniPickup\OmniPickup.exe`。

## Skill 整理追加任务
- [x] 完成 `OmniPickup` 最终 EXE 构建。
- [x] 在当前目录根部创建中文为主的 `SKILL.md`，描述脚本用法、注意事项、虚拟环境和打包流程。
- [x] 使用 Skill Creator 的校验脚本验证 `SKILL.md`，不创建新的 Skill 子目录；校验通过。
- [x] 将 `.cmd`/`.ps1` 入口改为优先调用当前目录 `.venv`，避免未激活环境时找不到 PyAudio。
- [x] 验证 `OmniPickup.exe` 的 WASAPI 设备格式校验；旧历史 build/dist 目录因安全策略阻止递归删除而保留，不作为当前 Skill 入口。

## 目录清理追加任务
- [x] 删除旧版 `build_recorderByDWWM`、`dist_recorderByDWWM`、`build_万能拾音器`、`dist_万能拾音器` 和 `__pycache__`。
- [x] 保留当前 `OmniPickup` 源码、入口脚本、spec、EXE、构建目录、虚拟环境、图标、`SKILL.md` 和 `plan.md`。
- [x] 修正 `SKILL.md` 中已不随当前目录保留的旧源码路径说明。
- [x] 清理后重新验证目录清单、Skill 校验和 `OmniPickup.exe -h`。

## 目录结构整理追加任务
- [x] 创建 `src`、`launchers`、`packaging`、`build` 和 `dist` 分类目录。
- [x] 更新启动器与 PyInstaller spec 的相对路径解析，再移动对应文件和当前构建产物。
- [x] 在 `SKILL.md` 中记录完整目录结构、入口命令和相对路径依赖。
- [x] 验证源码、启动器、EXE 帮助、Skill 校验和打包 spec 路径。

## Git 云端发布追加任务
- [x] 明确源码、启动器和打包命令必须使用随 Skill 提供的 `.venv`，只有 EXE 可脱离虚拟环境。
- [x] 使用 `skill-git` 将当前目录（包含 `.venv`）发布到同名 GitHub 仓库。
- [x] 验证远端仓库、提交和推送结果：远端 `main` 与本地发布缓存一致，已确认跟踪 `.venv` 的 Python、pip 与 PyAudio 文件。
