---
name: omni-pickup
description: "Windows 多 Host API 音频输入采集 Skill。用于使用当前目录的 OmniPickup 录音脚本或独立 EXE，按设备索引/名称选择 DirectSound、WASAPI、WDM-KS 或 ASIO 输入端点，自定义采样率、通道数、位深、录音时长并输出无文件头的原始 PCM；脚本、启动器和打包命令必须使用随 Skill 提供的 .venv，只有 EXE 可脱离虚拟环境运行；也用于设备枚举、格式校验、长时间录音和故障排查。"
---

# OmniPickup 音频采集

当前版本：`V1.0.1`

## 用途

使用 `src\OmniPickup.py` 或 `dist\OmniPickup.exe` 采集 Windows 音频输入设备，输出交错的原始 PCM 文件。脚本支持按 Host API、设备索引或设备名称选择输入端点，并可自定义采样率、通道数、位深、缓冲区和录音时长。

## 目录约定

- `src\OmniPickup.py`：源码入口。
- `launchers\OmniPickup.cmd`、`launchers\OmniPickup.ps1`：Windows 启动入口；启动器会自动回到 Skill 根目录解析依赖。
- `dist\OmniPickup_wait_listenai.bat`：可直接用于刷机流程的固定参数批处理入口，等待 `麦克风 (ListenAI Audio)` 出现后延迟 5 秒开始持续录音。
- `.venv\`：当前目录专用 Python 3.10 虚拟环境，不使用系统 Python 包。
- `packaging\OmniPickup.spec`：PyInstaller 配置，引用 `packaging\record_asio_pcm.ico` 图标和 `src\OmniPickup.py` 源码。
- `packaging\record_asio_pcm.ico`：EXE 图标资源。
- `dist\OmniPickup.exe`：独立单文件 EXE。
- `build\`：PyInstaller 中间构建文件，可在重新打包时重建。
- `SKILL.md`、`plan.md`：Skill 说明和执行记录。
- 旧版 ASIO 源码未随当前 Skill 保留；当前多 Host API 入口统一使用 `src\OmniPickup.py`。

## 相对路径依赖

所有相对路径都以 Skill 根目录（即本文件所在目录）为基准：

| 使用者 | 依赖目标 | 关系 |
| --- | --- | --- |
| `launchers\OmniPickup.cmd` | `.venv\Scripts\python.exe`、`src\OmniPickup.py` | 通过启动器目录的上一级定位 Skill 根目录 |
| `launchers\OmniPickup.ps1` | `.venv\Scripts\python.exe`、`src\OmniPickup.py` | 通过 `$PSScriptRoot\..` 定位 Skill 根目录 |
| `packaging\OmniPickup.spec` | `src\OmniPickup.py`、`packaging\record_asio_pcm.ico` | 通过 `SPECPATH` 的上一级定位 Skill 根目录 |
| `dist\OmniPickup.exe` | Windows 音频驱动和系统运行库 | 不依赖 `.venv` 或源码路径 |
| `build\` | `packaging\OmniPickup.spec` 的构建输出 | 仅为中间产物，不是运行时依赖 |

从 Skill 根目录执行命令最稳定；从其他目录调用启动器时，启动器仍能正确解析 `.venv` 和源码。录音输出路径则相对于命令执行时的当前工作目录。

## 运行环境矩阵

除独立 EXE 外，所有操作都必须使用 Skill 根目录中的 `.venv`：

| 操作 | 入口 | `.venv` 要求 |
| --- | --- | --- |
| 直接运行源码、列设备、格式校验、录音 | `.venv\Scripts\python.exe src\OmniPickup.py` | 必须使用 |
| CMD/PowerShell 启动器 | `launchers\OmniPickup.cmd`、`launchers\OmniPickup.ps1` | 启动器强制检查并使用 |
| 重新打包 EXE | `.venv\Scripts\python.exe -m PyInstaller ...` | 必须使用 |
| 运行独立 EXE | `dist\OmniPickup.exe` | 不需要 |

发布仓库包含 `.venv`，不要删除、移动或将其加入忽略规则；若 `.venv` 缺失，源码、启动器和打包命令应直接报错，而不是回退到系统 Python。

## 前置检查

1. 在当前目录执行命令，或使用 `.venv\Scripts\python.exe` 的绝对路径。
2. 直接运行源码时使用 `.venv\Scripts\python.exe`，不要依赖系统 `python`。
3. 录音前确认目标设备具有输入通道，并确认驱动已安装且未被其他程序独占。
4. 默认 Host API 是 `WASAPI`，默认设备名为空，表示选择该 Host API 下索引最小的可录音输入设备；正式任务建议先列设备再指定 `--device-index`。

## 常用操作

### 列出设备

默认列出所有可录音输入设备，并按 `ASIO`、`DirectSound`、`WASAPI`、`WDM-KS`、`Other` 分组。设备编号是 PortAudio 全局索引：

```powershell
    .\.venv\Scripts\python.exe .\src\OmniPickup.py --list-devices
```

输出结构类似：

```text
=== WASAPI ===
    --32
      麦克风 (设备名)
        host_api=Windows WASAPI inputs=8 outputs=0 default_rate=16000
```

只查看一种 Host API：

```powershell
    .\.venv\Scripts\python.exe .\src\OmniPickup.py --list-devices --host-api wasapi
```

可用 Host API 参数：`asio`、`directsound`、`wasapi`、`wdm-ks`。也接受 Windows 返回的别名，如 `Windows WASAPI`。

### 查看帮助

```powershell
    .\.venv\Scripts\python.exe .\src\OmniPickup.py -h
.\launchers\OmniPickup.cmd -h
.\launchers\OmniPickup.ps1 -h
```

### 录制固定时长

`--duration` 的单位是秒，支持整数或小数。下面示例录制 1 小时：

```powershell
    .\.venv\Scripts\python.exe .\src\OmniPickup.py `
  --host-api wasapi `
  --device-index 32 `
  --sample-rate 16000 `
  --channels 8 `
  --bit-depth 16 `
  --duration 3600 `
  --output .\recordings\one_hour.pcm
```

常用时长：`3600` 为 1 小时，`28800` 为 8 小时，`86400` 为 24 小时。

### 持续录音

省略 `--duration` 或传入 `--duration 0` 即为持续录音。按 `Ctrl+C` 停止；设备断开、流异常或输出写入失败也会停止并清理资源。

```powershell
    .\.venv\Scripts\python.exe .\src\OmniPickup.py `
  --host-api wasapi `
  --device-index 32 `
  --sample-rate 16000 `
  --channels 8 `
  --bit-depth 16 `
  --output .\recordings\continuous.pcm
```

### 使用设备名称选择

`--device-name` 支持标准化后的精确匹配和子串匹配；名称不确定时优先使用 `--device-index`。

```powershell
    .\.venv\Scripts\python.exe .\src\OmniPickup.py `
  --host-api wasapi `
  --device-name "ListenAI Audio" `
  --sample-rate 16000 --channels 8 --bit-depth 16 `
  --duration 60 -o .\recordings\listenai_60s.pcm
```

### 录音前校验

`--validate-only` 只枚举、选择并校验设备和格式，不创建录音文件：

```powershell
    .\.venv\Scripts\python.exe .\src\OmniPickup.py `
  --host-api wasapi --device-index 32 `
  --sample-rate 16000 --channels 8 --bit-depth 16 `
  --validate-only
```

### 等待声卡出现后录音

使用 `--wait-device-name` 时，脚本每 `0.2` 秒检测一次指定名称（支持标准化后的精确匹配或子串匹配）的输入设备，并在轮询过程中刷新 PortAudio 设备实例以识别热插拔。设备出现后先等待 `--device-appear-delay` 秒，再执行原有设备校验和录音流程；延迟默认是 `0` 秒。等待期间可以按 `Ctrl+C` 安全退出。

```powershell
.\.venv\Scripts\python.exe .\src\OmniPickup.py `
  --host-api wasapi `
  --wait-device-name "ListenAI Audio" `
  --device-appear-delay 5 `
  --sample-rate 16000 --channels 8 --bit-depth 16 `
  --duration 60 -o .\recordings\when_ready.pcm
```

未指定 `--device-name` 时，出现的目标声卡也会作为实际录音设备；如果同时指定了 `--device-name`，等待目标和实际录音目标可以分别设置。

刷机流程可以直接调用固定参数 BAT：

```bat
dist\OmniPickup_wait_listenai.bat
```

该 BAT 默认持续录音；可以在命令后追加原有参数，例如 `--duration 60 --output recordings\one_minute.pcm`。

### 使用独立 EXE

打包后的 EXE 不需要 `.venv` Python 启动：

```powershell
.\dist\OmniPickup.exe --list-devices
.\dist\OmniPickup.exe --host-api wasapi --device-index 32 `
  --sample-rate 16000 --channels 8 --bit-depth 16 --duration 3600 `
  -o .\recordings\one_hour.pcm
```

EXE 仍依赖 Windows 音频驱动和系统运行库，但不依赖当前目录的 Python 包。

## 参数说明

- `--host-api` / `--api`：选择 `asio`、`directsound`、`wasapi` 或 `wdm-ks`；默认 `wasapi`。
- `--device-index`：PortAudio 全局设备索引，来自 `--list-devices` 的 `--数字`。
- `--device-name`：设备名称或子串；默认空值，选择所选 Host API 下最小索引输入设备。
- `--wait-device-name`：等待出现的输入设备名称或子串；指定后设备未出现时持续等待。
- `--device-appear-delay`：检测到等待目标后、开始校验和录音前的延迟秒数，默认 `0`。
- `--sample-rate`：采样率，单位 Hz，例如 `16000`、`44100`、`48000`。
- `--channels`：输入通道数，例如 `1`、`2`、`8`。
- `--bit-depth`：`8`、`16`、`24` 或 `32` 位；必须由目标设备和 PortAudio 支持。
- `--frames-per-buffer`：每次从音频流读取的帧数，默认 `4800`。
- `--duration`：录音秒数；省略或 `0` 表示持续录音。
- `-o` / `--output` / `--name`：输出 PCM 路径；不指定时生成时间戳文件名。
- `--output-dir`：默认时间戳文件的目录，默认当前目录。
- `--list-devices`：列出输入设备；可配合 `--host-api` 过滤。
- `--validate-only`：只检查设备和格式，不录音。

## PCM 文件约定

输出文件是无 WAV 头的交错原始 PCM。解析时必须知道采样率、通道数、位深和字节序；默认位深使用 PyAudio 对应的有符号格式。固定时长的理论文件大小为：

```text
采样率 × 通道数 × 每样本字节数 × 秒数
```

脚本会检查每次读取的数据长度，发现短帧或设备流异常时停止，不把不完整数据静默当作成功。

## 设备与 Host API 注意事项

- 当前 `.venv` 的 `PyAudio 0.2.14` 实际提供 `MME`、`DirectSound`、`WASAPI`、`WDM-KS`；标准 wheel 未提供 `ASIO` Host API。
- 需要 ASIO 时，必须安装或自行构建带 ASIO 支持的 PortAudio/PyAudio，并重新列设备验证；不能仅凭脚本参数假定 ASIO 存在。
- 列表中的 `outputs` 只是端点能力信息；当前脚本只打开具有输入通道的设备进行录音。
- 普通 WASAPI 输出端点不是输入源；系统播放回录（WASAPI loopback）需要专门的 loopback 实现，本 Skill 当前不覆盖。
- 默认设备名为空会选择第一个匹配输入设备，可能不是用户想要的声卡；正式录音应显式指定 `--device-index` 或 `--device-name`。
- 不同 Host API 对采样率、通道数和独占/共享模式的支持不同；以 `--validate-only` 的实际结果为准。
- 设备索引是 PortAudio 全局索引，驱动变化、插拔设备或系统重启后可能变化，不能长期硬编码而不重新列设备。

## 虚拟环境与依赖

当前目录的 `.venv` 是本 Skill 专用环境，发布仓库会一并携带；创建和使用方式如下：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install PyAudio==0.2.14
.\.venv\Scripts\python.exe -m pip install PyInstaller
```

不要用系统 Python 的 `pip` 安装或卸载这些依赖。执行前可检查：

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -c "import pyaudio; print(pyaudio.__version__)"
```

## 重新打包

使用当前目录的 spec 和图标重新生成 EXE：

```powershell
    .\.venv\Scripts\python.exe -m PyInstaller `
  --noconfirm --clean `
  --distpath .\dist `
  --workpath .\build `
  .\packaging\OmniPickup.spec
```

`packaging\OmniPickup.spec` 使用 `packaging\record_asio_pcm.ico`；打包后至少验证：

```powershell
.\dist\OmniPickup.exe -h
.\dist\OmniPickup.exe --list-devices
```

## 故障排查

- `PyAudio is not installed`：确认命令使用 `.venv\Scripts\python.exe`，不要使用系统 `python`。
- `No ... input device matched`：先执行 `--list-devices`，检查 Host API、索引和名称，再显式指定。
- `only exposes ... input channels`：降低 `--channels` 或换一个具有足够输入通道的端点。
- `Requested format is not supported`：以设备默认采样率为起点调整 `--sample-rate`、`--channels` 和 `--bit-depth`，先用 `--validate-only`。
- `The device may have been disconnected`：检查 USB/驱动、电源管理和其他占用音频设备的程序。
- 录音文件无法播放：确认播放器按 raw PCM 打开，并输入与录音命令一致的参数；该文件没有 WAV 头。

## 退出码

- `0`：设备列出、校验或录音成功完成。
- `2`：参数、依赖、设备、格式、流或输出文件错误。
- `130`：用户通过 `Ctrl+C` 中断录音。
