# ffta-us-cn

简体中文 | [English](README.en.md)

**《最终幻想战略版 Advance》（FFTA）GBA 美版的汉化构建与插件模板。**

本项目以美版汉化 v1.1 为基础，集成拼音命名、串行通信超时修复和标题菜单 Info。你可以直接构建默认版本，也可以 fork 后在 `plugins/` 中添加自己的插件。

**默认输出为 16 MiB ROM；也提供精确复现汉化参考版的构建模式。** 游戏 ROM 由用户自行提供，不随源码分发。

## 主要功能

| 功能 | 内容 |
| --- | --- |
| 汉化集成 | 导入汉化 v1.1 的文本、字库、图片和资源加载逻辑，支持逐字节复现指定参考 ROM |
| 拼音命名 | 用拼音输入中文名字；替换第一页键盘，保留第二页原生键盘，不增加第三个标签页 |
| 串行超时修复 | 调整串行通信计数器的超时比较阈值，可单独关闭 |
| 插件信息界面 | 在标题菜单加入 Info，显示插件名称与作者说明，支持分页和自动换行，按 **B** 关闭 |
| 插件与字库扩展 | 本地插件直接放在 `plugins/`；支持追加样式字形并生成更新后的字表，默认用于 Info 斜体入口 |

以上功能在默认构建中启用。汉化基础字库拥有最高优先级，追加字形不改变原有字形编码。

## 快速开始

本地构建需要 **Git、Python 3.12+、Clang、Make 和 ARM binutils（`arm-none-eabi-*`）**。Python 工具仅使用标准库；构建入口负责拉取固定版本依赖并构建所需编译器。

### 1. Fork 并配置 ROM 私库

Fork 本仓库，在本地克隆你的 fork。另建一个私有仓库，在根目录放入以下两个 ROM：

```text
ffta-us.gba
ffta-us-cn-v1.1.gba
```

文件名用于方便辨认，实际版本由 SHA-256 确认。直接存放 ROM 即可；已有的 `inputs.zip` 也兼容读取。

在**个人 fork 的根目录**创建 `rom-source.txt`，只写一行私库地址。例如，将 `YOUR_USER` 替换为你的 GitHub 用户名：

```text
https://github.com/YOUR_USER/ffta-roms.git
```

可从 `rom-source.example.txt` 复制后修改。真实地址只保存在个人 fork；组织模板不包含用户配置，没有这个文件时会跳过 ROM 构建。

### 2. 本地构建

在源码根目录执行，私库访问使用你已有的 Git 登录凭据：

```sh
python3 tools/ci_private_build.py \
  --work-dir ../private-build --publish-dir ../patches --profile default
```

脚本会自动拉取公共依赖和 ROM 私库、校验输入、导入汉化资源，再完成编译。**每次构建使用新的外部工作目录**，不要把输入和输出放进源码仓库。

| 产物 | 默认示例路径 |
| --- | --- |
| 完整 ROM | `../private-build/build/ffta-us-cn.gba` |
| 相对于美版原版的 IPS 补丁 | `../patches/ffta-us-cn.ips` |
| 输入提交、ROM 哈希及构建报告 | `../patches/build-report.json` |

### 3. 使用 GitHub Actions 构建

将 `rom-source.txt` 提交到个人 fork，并配置一个 Secret：**`PRIVATE_ROM_SSH_KEY`**，内容为 ROM 私库的只读 deploy key 私钥。Actions 的默认令牌无法读取另一个私库，因此仍需要这项授权；无需再配置仓库地址、提交号或启用开关等变量。

打开个人 fork 的 **Actions → Private ROM build (manual opt-in) → Run workflow**，选择构建模式后运行。流程只允许手动触发，不会在 push、PR 或定时任务中自动构建。

**Actions 默认只上传 IPS 和校验报告，不上传完整 ROM。** 完整 ROM、字体和资源包应保存在私有环境。详细配置见[私库与构建指南](docs/private-rom-workflow.md)。

## 选择构建模式

| `--profile` / Actions 选项 | 适用场景 |
| --- | --- |
| `default` | 使用汉化、拼音、串行超时修复和 Info，或开发自己的插件 |
| `exact-reference` | 仅保留参考汉化，关闭拼音、串行超时修复和 Info，检查输出是否逐字节一致 |

如果自行添加了会修改 ROM 的插件，复现参考版前也需要关闭这些插件。英文基线及独立功能开关见下方的高级选项。

## 添加自己的插件

1. 将 `examples/plugin-template/build.py` 复制到 `plugins/my_plugin/build.py`。
2. 把 `examples/plugin-template/declaration.json` 中的示例声明加入 `plugins/plugins.json`。
3. 在插件入口中实现自己的源码或资源扩展；示例本身为空实现，不会改变 ROM。
4. 执行 `python3 tools/plugin_projects.py sync` 更新源码哈希锁，再按正常流程构建。

构建会自动加载已启用的插件，不需要修改主构建脚本或再次注册。一个插件项目可以声明多个插件；引用外部项目时，只导入其清单中声明的文件，不自动引入内部依赖或测试内容。

详见[本地插件指南](plugins/README.md)、[插件项目约定](docs/plugin-projects.md)和[字库扩展](docs/font-plugins.md)。

### 目录分工

| 路径 | 用途 |
| --- | --- |
| `plugins/` | 本项目维护的插件源码，包括 Info |
| `engine/` | 汉化加载、原生命名入口和拼音核心的 C/ASM 实现 |
| `config/` | 资源布局、字符映射、插件配置与依赖锁 |
| `tools/` | 依赖拉取、资源导入、构建和验证工具 |
| `vendor/` | 按固定 Git 版本拉取的外部依赖，不纳入版本控制或源码包 |

**在自己的源码目录开发，不要修改或提交 `vendor/` 内容。** 通用引擎接口应提交到上游，再更新锁定版本。详见[依赖说明](docs/dependencies.md)和[项目约定](AGENTS.md)。

## 验证与打包

拉取依赖后，可执行：

```sh
python3 tools/verify_vendor.py
python3 -m unittest discover -s tests
python3 tools/package_source.py --output "$SOURCE_ARCHIVE"
```

`$SOURCE_ARCHIVE` 必须指向项目外的输出路径。源码包包含项目源码和依赖锁，不包含依赖实现、ROM、字体、资源包或构建缓存；解压后执行 `python3 tools/fetch_dependencies.py` 拉取依赖及原始许可证。

验证构建确定性时，在两个全新的外部目录中构建并比较最终 ROM 哈希。`exact-reference` 会进一步检查输出是否与汉化参考版一致。

### 实现与验证范围

- 本项目通过上游构建扩展接口应用源码和资源替换。当前会编译并精确校验 5 个已反编译的命名入口，对应 1,700 字节原始代码；其余原版代码仍来自已验证的美版 ROM，尚非全游戏源码重建。
- 新增功能不计入反编译匹配成果。串行超时修复不代表新增 GP 模式；函数级模拟器测试也不能替代真实联机、硬件或存档读写验证。
- 仓库保留了所有者提供的第三方汉化字符映射及来源记录，详见[字表说明](config/charsets/us-cn-v1.1/README.md)。原生字库像素、提取文本及其他游戏资源由用户输入提供。

<details>
<summary>高级：独立功能开关与英文基线</summary>

以下参数用于底层入口 `tools/build.py`，不是上面的 `ci_private_build.py`。该入口需要显式提供 ROM、资源包和相应字表输入，详见[精确构建说明](docs/us-cn-exact-build.md)。

| 参数 | 结果 |
| --- | --- |
| `--disable-pinyin` | 保留汉化和串行超时修复，关闭拼音输入 |
| `--disable-pinyin --disable-link-fix` | 精确复现汉化参考版，同时关闭默认 Info 和斜体扩展 |
| `--disable-cjk` | 构建英文基线，默认关闭拼音、串行超时修复和 Info |
| `--disable-cjk --enable-link-fix --disable-info` | 英文基线，仅启用串行超时修复 |
| `--disable-info` | 关闭标题菜单 Info，默认也不生成其斜体字形 |
| `--disable-italic-font` | Info 入口使用原字库正体 |

不能同时使用 `--disable-cjk` 和 `--enable-pinyin`。若显式启用斜体，则必须同时启用汉化基础字库和 Info。

</details>

<details>
<summary>输入 ROM 的 SHA-256 校验值</summary>

两个输入均为 16 MiB，仅接受以下固定版本：

| 输入 | SHA-256 |
| --- | --- |
| 美版零售 ROM | `43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19` |
| 美版汉化 v1.1 参考 ROM | `ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03` |

</details>

## 深入阅读

| 主题 | 文档 |
| --- | --- |
| 汉化参考版的导出与字节匹配 | [资源导出](docs/us-cn-resource-export.md) · [精确构建](docs/us-cn-exact-build.md) |
| 拼音输入的行为与验证范围 | [原生拼音命名](docs/native-pinyin-names.md) |
| 标题菜单和插件信息界面 | [Info 界面](docs/plugin-info.md) |
| 串行通信修复 | [超时修复说明](docs/link-timeout-fix.md) |
| 依赖来源与版权说明 | [依赖说明](docs/dependencies.md) · [NOTICE](NOTICE.md) |
