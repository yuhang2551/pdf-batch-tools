# PDF Batch Tools

**中文** | [English](README_EN.md)

基于清单（manifest）驱动的整页变换工具，带预检校验，保留源文件，并为每个文件生成证据。

[详细案例：问题、数据、方法、证据与局限（英文）](CASE_STUDY.md)

![PDF 批处理演示](portfolio-cover.png)

**这是一个独立的工程演示，使用自制的示意 PDF，不是客户文件或施工图纸。**

## 复现

需要 Python 3.10+、pypdf 和 ReportLab。

    python -m pip install -r requirements.txt
    python -m unittest -v
    python demo.py --output demo-output
    python pdf_batch.py jobs.json --output new-results

每次运行请使用新的输出目录。演示会生成 80 个单页 PDF，每种操作各处理 20 个，并写出一份输出清单，包含 SHA-256 哈希、页数和页面尺寸。

## 清单约定

    {
      "version": 1,
      "jobs": [
        {
          "input": "inputs/schematic.pdf",
          "output": "mirrored.pdf",
          "operation": "mirror_horizontal"
        }
      ]
    }

支持的操作：`mirror_horizontal`、`mirror_vertical`、`rotate_180` 和 `copy`。输入路径必须位于清单所在目录内；输出名必须是简单且不重复的 PDF 文件名。

## 已验证的演示

- 80 个输入文件和 80 个输出文件，每个都是单页。
- 全部 80 对输入/输出都以 72 DPI 渲染，并与要求的几何变换进行比对。详细测量数据见 `render_verification.json`。
- 这 80 个文件是同一个自制模板的编号实例，不是 80 种独立的文档类型。平均 RGB 误差上限为 2.0（0-255 刻度），这不是百分比准确率。
- 13 个自动化测试覆盖：结构保留、源文件哈希、不支持的输入、重复文件名、路径穿越、预检失败和禁止覆盖。
- 提供了有代表性的变换前后 PDF：`sample_input.pdf` 和 `sample_mirrored.pdf`。

## 重要边界

**整页镜像会把文字也一起镜像。** 只翻转图形几何、同时保持标注文字可读，是另一种需求，本项目没有实现。在处理客户图纸之前，请先确认这一区别。

表单、注释、文档动作、命名或嵌入对象、旋转过的输入页、非默认用户单位，以及非零或不一致的 media/crop box 都会被拒绝，需要单独处理。限制：每个输入 20 MiB，每个文件 100 页，500 个任务，每批预备输出 100 MiB。

在创建输出之前会先对输入做预检。磁盘错误仍可能留下不完整的新输出目录，也没有断点续跑或自动上传流程。本工具不是用来处理恶意 PDF 的安全沙箱，也不保证对任意 PDF 的保真度。渲染验证只覆盖所提供的合成测试数据，不覆盖所有 PDF 生成工具或客户系统。

## 项目说明

安装 Pillow 和 Poppler 后，运行 `verify_rendering.py demo-output --output render-check` 可以重复单页测试数据的比对。具体环境和命令见详细案例。`verification.json` 记录了测试方法和源码哈希。

源码、测试数据和验证流程共同说明了演示的能力。不涉及任何客户文件、受限图纸或建筑相关资质。
