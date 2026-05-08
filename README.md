# aka-semi-utils / 极简水印

> [![release](https://img.shields.io/github/v/release/BakaAkari/aka-semi-utils)](https://github.com/BakaAkari/aka-semi-utils/releases)
> [![downloads](https://img.shields.io/github/downloads/BakaAkari/aka-semi-utils/total.svg)](https://github.com/BakaAkari/aka-semi-utils/releases)
> [![license](https://img.shields.io/github/license/BakaAkari/aka-semi-utils)](LICENSE)
> ![language](https://img.shields.io/github/languages/top/BakaAkari/aka-semi-utils?color=orange)
>
> **极简水印是一个面向摄影照片的 PyQt6 图形化批量水印工具，支持 EXIF 信息水印、品牌 Logo、签名水印、实时预览和三平台打包发布。**

本项目基于 semi-utils 的图片处理能力继续改造，重点补齐桌面 GUI、批处理体验、配置持久化、实时预览、错误汇总和跨平台打包发布流程。

## 功能特性

- **图形化操作**：拖拽或选择照片，配置后点击 `START` 批量处理。
- **EXIF 水印**：可组合相机型号、镜头、焦距、光圈、快门、ISO、拍摄时间等字段。
- **四角文本布局**：左上、左下、右上、右下独立配置字段、分隔符、字体和颜色。
- **品牌 Logo**：内置常见相机 / 手机品牌 Logo，并支持替换自定义 Logo。
- **签名水印**：支持导入签名图片、九宫格定位、宽度比例、边距、偏移以及黑白反转。
- **实时预览**：右侧可折叠预览栏，配置变化后可快速查看渲染效果。
- **高级处理**：支持留白、圆角、阴影、模糊背景、缩放、拼接、质量设置等处理项。
- **批量处理**：后台线程执行任务，展示进度、失败详情和处理结果汇总。
- **三平台发布**：GitHub Actions 自动构建 Windows、macOS、Linux Release 包。

## 下载使用

在 [Releases](https://github.com/BakaAkari/aka-semi-utils/releases) 页面下载对应平台的压缩包：

- Windows：下载 Windows 包，解压后运行应用程序。
- macOS：下载 macOS 包，解压后运行应用程序；如遇系统安全提示，请在系统设置中允许打开。
- Linux：下载 Linux 包，解压后运行可执行文件。

> 程序依赖 `exiftool` 读取照片元数据。Release 包会尽量随平台构建流程准备运行环境；本地开发运行时请确保系统可访问 `exiftool`。

## 本地开发

项目使用 Python 3.13 和 `uv` 管理依赖：

```bash
uv sync
uv run python main.py
```

常用检查命令：

```bash
uv run ruff check .
uv run mypy .
uv run pytest
```

## 打包发布

本仓库提供 PyInstaller spec 和 GitHub Actions 三平台构建流程：

- 通用 spec：`scripts/build.spec`
- Release workflow：`.github/workflows/build-release.yml`
- CI workflow：`.github/workflows/ci.yml`

推送版本 tag 后会触发三平台构建并上传 Release assets。

## 效果展示

以下示例模板来自项目内置静态资源，可作为 GUI 配置和处理管线的参考：

| 模板 | 描述 | 效果 |
| --- | --- | --- |
| [standard1](./static/standard1.json) | 经典 EXIF 水印，包含相机型号、镜头、焦距、光圈、快门、ISO、拍摄时间和相机品牌 Logo | ![standard1](./static/standard1.jpeg) |
| [standard2](./static/standard2.json) | 在 standard1 基础上添加圆角、阴影效果和留白，适合社交媒体分享 | ![standard2](./static/standard2.jpeg) |
| [nikon_blur](./static/nikon_blur.json) | 尼康风格水印，相机型号中的红色「Z」字高亮，配合模糊背景效果 | ![nikon_blur](./static/nikon_blur.jpeg) |
| [blur](./static/blur.json) | 简洁风格，相机型号与参数垂直居中展示，配合模糊背景效果 | ![blur](./static/blur.jpeg) |
| [normal1](./static/normal1.json) | 极简风格，右下角显示拍摄参数，低调不抢眼 | ![normal1](./static/normal1.jpeg) |
| [normal2](./static/normal2.json) | 文件夹名称 + 拍摄时间，橙色文字，简洁实用 | ![normal2](./static/normal2.jpeg) |
| [center_logo](./static/center_logo.json) | 中心 Logo 水印，可自定义四周文字内容 | ![center_logo](./static/center_logo.jpeg) |

## 项目结构

```text
main.py                 # PyQt6 GUI 入口
gui/                    # GUI 界面、状态管理、预览和批处理线程
processor/              # 图片处理管线与滤镜实现
core/                   # 配置、EXIF、字体、日志和通用工具
config/                 # 默认配置、字体、Logo、模板目录
static/                 # 示例模板与效果图
scripts/build.spec      # PyInstaller 打包配置
.github/workflows/      # CI 与 Release 自动化
```

## 许可证

aka-semi-utils 基于 [Apache License 2.0](LICENSE) 发布。

### exiftool

项目使用 [exiftool](https://exiftool.org/) 读取照片 EXIF 信息。exiftool 基于 [GPL v1 + Artistic License 2.0](https://exiftool.org/#license) 发布。

## 关于

- 项目地址：[BakaAkari/aka-semi-utils](https://github.com/BakaAkari/aka-semi-utils)
- 当前版本：`2.1.6`
- 主要形态：PyQt6 桌面 GUI + 批量图片水印处理管线
