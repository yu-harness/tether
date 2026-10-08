# pico 工作约定

这个目录是 pico 本体。解释器用 `D:/Dev/miniconda3/python.exe`，本机只有它装齐了依赖。

## 提交前跑这三条

- 单元测试：`D:/Dev/miniconda3/python.exe -m pytest tests -q`
- 固定任务门禁：`D:/Dev/miniconda3/python.exe scripts/ci_regression.py`（合成模式跑 18 个固定任务，约 40 秒，不是全部通过就返回非零）
- 文档路径检查：`D:/Dev/miniconda3/python.exe scripts/check_doc_paths.py`

## 数字的规矩

- 对外数字只有一处来源：`数据卡片.md`。报数字按卡片里的写法报，每条都带来源文件与复现命令
- 改了 prompt 模板、上下文段落、固定任务集之后，必须重跑 `scripts/reproduce_resume_archive.py`，把 `数据卡片.md` 里的数字同步过来
- 合成模式（FakeModelClient 脚本输出）与真实模式（deepseek-flash）的数字回答的是不同问题，不允许互相代替
- 真实模式带 temperature，重复跑有个别任务的结果波动，报数字要带上测量时间

## 写代码的规矩

- 出错就地报错，不写兜底分支，不做静默降级
- 测试与脚本里不出现 mock 与假数据，验证要调用真实代码路径
- 注释用中文，标识符保留英文原名
- 不新增用不到的配置项与抽象层

## 新缺陷怎么处理

- 每个平台级缺陷先写一个 pytest 用例，`tests/test_platform_regressions.py` 是现成的例子
- 能用脚本化模型在 fixture 工作区里复现的，再补一个 `platform-regression` 类别的固定任务进 `benchmarks/coding_tasks.json`
- 新任务的 verifier 写进 `tests/fixtures/bench_repo_platform/`，需要调用 pico 代码时读 `PICO_BENCHMARK_REPO_ROOT`
