# ffta-us-cn

简体中文 | [English](README.en.md)

Final Fantasy Tactics Advance 美版的可选汉化与拼音命名扩展，与固定版本的反编译源码依赖联合构建。**默认启用汉化和拼音输入**，汉化构建也默认启用串行通信计数器超时修复。ROM 保持 16 MiB，保留原生字形编号、文本与控制符语义，以及原有的两种标签页样式。拼音输入替换第一页键盘，第二页原生键盘仍可使用，不新增第三个标签页。

| 构建参数 | 结果 |
| --- | --- |
| 默认 | 汉化资源与加载逻辑、拼音命名、串行超时修复、标题菜单 Info，以及追加的斜体入口字形 |
| `--disable-pinyin` | 启用汉化和串行超时修复，关闭拼音输入 |
| `--disable-pinyin --disable-link-fix` | 精确复现固定版本的 16 MiB 汉化参考 ROM |
| `--disable-cjk` | 英文基线，自动关闭拼音输入 |
| `--disable-cjk --enable-link-fix --disable-info` | 英文基线，仅启用串行超时修复 |
| `--disable-cjk --enable-pinyin` | 参数相互矛盾，拒绝构建 |
| `--disable-italic-font` | 保留原字库，Info 入口使用正体 |

字库插件在 `plugins.json` 中声明字表、源字库布局和优先级。美版汉化 v1.1 基础字库拥有最高优先级；样式插件通过追加字形单元并生成更新后的字表实现扩展，不改变原有字形编码。详见[字库扩展](docs/font-plugins.md)。

一个插件项目可以通过文件清单导出多个插件。本地插件直接从 `plugins/` 读取，固定 Git 版本的外部插件导入 `vendor/plugins/`，只使用清单中声明的文件。详见[项目结构](docs/plugin-projects.md)。

## Fork 后添加插件

Fork 本仓库，将 `examples/plugin-template/build.py` 复制到 `plugins/my_plugin/build.py`，再把示例声明加入 `plugins/plugins.json`。执行 `python3 tools/plugin_projects.py sync` 后，按正常流程构建即可。构建系统会自动加载已启用的声明，无需修改主构建脚本或进行第二次注册。在实现扩展清单之前，示例插件不会改变 ROM。

本地源码在 `plugins/` 中开发，`vendor/` 用于保存固定版本的外部源码。详见[本地插件指南](plugins/README.md)和[构建入口约定](docs/plugin-projects.md)。

需要私有输入时，在个人 fork 的根目录添加 `rom-source.txt`，只写一行 ROM 私库的 Git 地址。[用户构建入口](docs/private-rom-workflow.md)会在本地构建和手动 Actions 构建时读取这个文件，无需配置仓库地址、提交号或启用开关等变量。Actions 只需配置私库的只读 deploy key。模板不包含真实输入配置，默认跳过 ROM 构建。

## 源码归属

汉化相关的 C/ASM 位于 `engine/`，其中 `engine/extensions/` 保存完整的命名入口替换实现。资源规则和指针布局规则由本项目维护。Info 在 `plugins/info/` 中维护并直接编译。

`vendor/` 保存按固定提交拉取的 Git 工作副本，包括官方反编译源码与工具、其编译器子模块，以及带许可证的 Rime 词典。这些依赖源码被 Git 忽略，不提交到模板，也不放入模板源码包。拼音核心由本项目维护，位于 `engine/pinyin/`。构建不依赖相邻的 decomp 工作目录或额外环境变量。

**不要修改 vendor 中的代码。** 通用构建接口的改动应提交到上游，参见[官方扩展接口 PR](https://github.com/ffta-decomp/fftadecomp/pull/1)。依赖锁固定到已合并的上游提交 `4ecb640abb607decd2581383e27604e3caaee280`，本项目不对依赖源码施加本地补丁。详见 [AGENTS.md](AGENTS.md) 和[依赖来源说明](docs/dependencies.md)。

兼容构建会编译五个已公开的原生命名 C 入口，对应 1,700 字节原始代码，并与美版零售 ROM 逐字节比较，再应用所选源码和资源扩展。拼音功能通过上游扩展接口替换三个完整源码模块，不覆盖 vendor 中的 C 文件，也不按字节偏移修改这些 C 函数的调用点。

其他游戏代码仍由已验证的原始输入提供，本项目并不声称已通过恢复的源码重建整个游戏。可选功能和修改版的输出不计入反编译匹配成果。

## 输入与构建环境

需要 Git、Python 3.12+、Clang、Make 和 ARM binutils（`arm-none-eabi-as`、`ld`、`objcopy`、`nm`）。核心构建工具仅使用 Python 标准库。编译器引导构建采用串行方式，在项目外的工作目录进行，并在成功后清理该临时工作目录。也可以通过 `--compiler` 显式指定已有的兼容编译器；报告会记录其哈希及原生基线的精确校验结果。

以下资源应保存在仓库和源码包之外：

- 美版零售 ROM：SHA-256 为 `43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19`。
- 汉化参考 ROM，仅用于本地导入和验证：SHA-256 为 `ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03`。
- 已导入的私有组件包、原生字形映射及其来源报告。
- 推导字形映射时显式提供的源字体和字符集输入。

本仓库不分发 ROM、提取的游戏文本、字体、存档或截图。所有者提供的第三方 v1.1 字符映射表保存在 `config/charsets/us-cn-v1.1/`，包含来源记录和 18 个样本的对比结果。构建读取美版零售 ROM 与私有组件包，不直接把汉化 ROM 作为输出，也不导入整份 ROM 的二进制差分。

## 导入一次，随后构建

以下命令在仓库根目录执行。变量应指向你显式选择的外部输入和全新输出目录，工具不会自动搜索资源。

```sh
python3 tools/fetch_dependencies.py
python3 tools/verify_vendor.py
python3 tools/migrate_us_cn.py import \
  --retail "$US_ROM" --translated "$CN_ROM" --pack-dir "$PRIVATE_PACK"

python3 tools/map_native_pinyin_glyphs.py \
  --translated "$CN_ROM" --source-font "$SOURCE_FONT" \
  --source-charset "$SOURCE_CHARSET" --output-dir "$GLYPH_MAP_DIR"

# 默认：汉化与拼音。Rime 源码及 Apache 许可证已在上面拉取。
python3 tools/build.py --retail "$US_ROM" --pack-dir "$PRIVATE_PACK" \
  --glyph-map "$GLYPH_MAP_DIR/glyph-map.json" \
  --map-report "$GLYPH_MAP_DIR/map-report.json" --output-dir "$OUTPUT"

# 精确复现汉化参考版，关闭拼音和新增的串行超时修复。
python3 tools/build.py --retail "$US_ROM" --pack-dir "$PRIVATE_PACK" \
  --disable-pinyin --disable-link-fix --output-dir "$EXACT_CN_OUTPUT"

# 原版英文基线。
python3 tools/build.py --retail "$US_ROM" \
  --disable-cjk --output-dir "$EN_OUTPUT"
```

最终文件为 `ffta-us-cn.gba`。`features.json` 记录源码与依赖哈希、功能选项、实际编译入口的空间范围和输出身份。生成的 `extension.json`、二进制片段及编译报告均保存在项目外。每次构建应使用全新输出目录。

添加 `--patch-output "$LOCAL_PATCH"` 可同时生成相对于已验证美版输入的确定性 IPS，并检查补丁应用后的完整还原结果。生成的补丁包含本地游戏资源，应保持私有，不纳入源码包。

[串行超时修复](docs/link-timeout-fix.md)是由源码汇编生成的 Thumb 比较指令扩展，不是恢复的 C 函数，也不是新增的 GP 模式实现。联机双方必须选择相同 ROM 和功能参数，并比较完整 ROM 哈希。直接调用函数的模拟器测试不能证明真实联机支持。

## 打包与验证

```sh
python3 -m unittest discover -s tests -v
PYTHONPATH=tools python3 -m unittest discover -s tools -p test_convert_ffta_us_cn.py
python3 tools/package_source.py --output "$SOURCE_ARCHIVE"
```

确定性源码包包含项目源码和依赖锁，不包含 `vendor/`、`.git`、构建缓存、ROM 或私有资源。解压后执行 `python3 tools/fetch_dependencies.py`，拉取固定版本的公共源码及原始许可证。构建前后都应验证依赖。

验证构建确定性时，使用两个全新的外部目录并比较最终 ROM 哈希；源码清单可能包含各自显式指定的输出路径。

进一步说明见[原生拼音行为与模拟器测试范围](docs/native-pinyin-names.md)、[精确资源导入](docs/us-cn-exact-build.md)和[已观察到的汉化地址布局](docs/us-cn-translation-layout.md)。旧版 ROM 构建工具和 32 MiB 演示工具仅作为历史诊断保留，不是当前联合构建入口。需要完整可写引擎工作副本的历史演示，必须显式选择独立开发目录。

[持久化参考资源导出器](docs/us-cn-resource-export.md)导出原生字形、文本、资源及 IPS 元数据，并验证整份 ROM 的字节匹配。可选的[标题菜单 Info 界面](docs/plugin-info.md)从 `plugins.json` 读取插件信息，可通过 `--disable-info` 关闭。
