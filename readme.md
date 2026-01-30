# ProBindBench 项目说明文档

## 1. 任务目标、定位与核心价值

### 任务目标
本项目（ProBindBench）旨在构建一个 **统一的、多模态的蛋白质结合体（Binder）设计与评估平台**。它专注于解决针对特定蛋白质靶点生成和筛洗高亲和力结合分子的问题，涵盖了 **多肽（Peptide）**、**小分子（Small Molecule）** 和 **抗体（Antibody）** 等多种药物/配体形式。

### 项目定位
*   **多模态生成引擎**：基于深度学习的分子生成和优化核心（UniMoMo）。
*   **全流程筛选平台**：集成从生成、构象优化到生物物理指标评估（Docking, Energy, Structural Analysis, 以及可能的MD Analysis）的一站式工作流。
*   **基准测试（Benchmark）**：为不同类型的分子生成算法提供标准化的评估环境。

### 核心价值

*   系统化的评价与验证体系能够：
    * 有效约束和引导protein binder 的 de novo设计模型的研发方向，
    * 避免模型仅针对低价值 benchmark 进行过拟合优化。
*   高通量且可扩展的筛选流程：
    * 可以显著降低计算与湿实验的成本，
    * 提升了 AI 设计结果的命中率和实际应用价值。
*  通过 Web Server 实现可视化筛选交互。
    * 支持通过图形界面评测，筛选以及序列结构预览
    * 系统支持结合能优化功能，便于连续开展多轮筛选。

## 2. 环境安装方法

本项目依赖以下环境，集成了多种生物计算工具。

### 2.1 基础环境配置 (Conda)

已在项目根目录提供了完整的环境配置文件 `environment.yml`，包含模型训练、评估及服务器运行所需的所有依赖。

```bash
# 创建并激活环境
conda env create -f environment.yml
conda activate probindbench
```

该环境文件已包含 PyTorch (CUDA 12.4), RDKit, OpenMM, Biopython 等核心库。

### 2.2 核心生物计算工具安装

虽然 `environment.yml` 中已集成大部分工具，但部分核心工具建议确认安装或需特殊授权：

#### OpenBabel (小分子处理)
通常包含在环境文件中，如需手动安装或排查问题：
```bash
conda install -c conda-forge openbabel
# 验证安装
obabel -V
```

#### AutoDock Vina (分子对接)
用于小分子的对接评分：
```bash
conda install -c bioconda vina
# 验证安装
vina --version
```
#### FoldX (结合能预测)

在[Foldx官网](https://foldxsuite.crg.eu/)上申请并且下载对应的可执行文件，放在`evaluation/dG/foldx5`中即可。
#### PyRosetta (高精度能量评估)
**注意**：PyRosetta 需要学术/商业授权。请访问 [PyRosetta官网](https://www.pyrosetta.org/downloads) 获取授权账号。

获取授权后，可通过以下方式安装（推荐使用 Conda）：

```bash
# 替换 user 和 password 为你的授权账号信息
conda install -c https://user:password@conda.graylab.jhu.edu pyrosetta
```
或者下载 whl 包进行安装。



## 3. 目前拥有的功能

### 3.1 Binder优化 (Generative Core)

*   **Binder优化 (Optimization)**：对初始结构进行进一步采样优化，提升亲和力和几何合理性。

### 3.2 评估与多轮筛选 (Screening & Evaluation)
*   **Web 筛选服务**：提供图形化前端界面，支持批量上传 PDB 文件。
*   **集成指标库**：
    *   **结合能评估**：FoldX (相互作用能), Rosetta (全原子能量), Vina (对接打分)。
    *   **结构质量**：Clash Score (原子碰撞检测)。

## 4. 使用方法

### 4.1 启动筛选服务器 (Screening Server)
用于可视化地管理任务和运行评估。此命令会启动 FastAPI 后端服务。

```bash
# 在项目根目录下运行
conda activate probindbench
python -m screening.server
```
启动后访问 `http://localhost:8000` 即可使用 Web 界面。

### 4.2 任务创建与筛选
1.  **文件上传**：在网页端上传 PDB 文件或 ZIP 压缩包。
2.  **链设置**：指定受体链 (Receptor Chain) 和 配体链 (Ligand Chain)。
3.  **运行任务**：创建 Job 后，文件状态显示为 "pending"。勾选 Vina/FoldX/Clash 等指标，点击 **Run** 开始并行计算。
4.  **结果查看**：点击 PDB 文件名可进行 3D 结构与序列预览。左侧侧边栏可根据计算指标筛选优质结果。

### 4.3 Binder 优化 (Optimization)
在 PDB 文件详情页点击 **Affinity Optimization** 按钮：
1.  设置优化参数（如优化步数）和生成样本数。
2.  系统后台调用生成模型对当前 Binder 进行结构微调。
3.  优化完成后，新生成的结构会自动转化为新的评测任务，可直接进行下一轮筛选。

注意：需要Unimomo的源代码以及 trained weights

## 5. 核心原理和思路

1.  **统一表征 (Unified Representation)**：
    *   将不同类型的生物分子（蛋白、小分子）映射到统一的隐空间（Latent Space）或几何表征中，使得模型可以跨模态学习物理相互作用规律。

2.  **生成模型 (LDM & Iterative AE)**：
    *   采用 **潜在扩散模型 (Latent Diffusion Models, LDM)** 或迭代自编码器，在隐空间进行去噪生成，然后解码回三维坐标。这保证了生成结构的多样性和分布的合理性。

3.  **基于先验的优化**：
    *   **Binder优化**：以当前 Binder 为条件/先验，使用扩散模型进行重采样（Resampling）或梯度引导，在保持原有骨架特征的同时优化结合界面的亲和力。

4.  **分级筛选 (Hierarchical Screening)**：
    *   思路是“先生成，后过滤”。利用生成模型的高通量特性产生大量候选，再通过筛选 Pipeline 中的低精度（如 Clash, Vina）到高精度（如 FoldX, Rosetta）指标进行逐级漏斗筛选，平衡计算成本与准确率。

## 6. 能力边界和下一步发展方向

### 能力边界
*   **计算资源**：评估模块（尤其是 Rosetta 和 FoldX）对 CPU 性能要求较高，大规模筛选需高算力支持。
*   **评测方法**：目前的评估主要基于静态结构的能量函数打分，未充分考虑蛋白质在溶液中的动态构象变化，例如分子动力学模拟等。
*   **湿实验验证**：目前的生成和筛选流程主要基于计算指标，尚缺乏大规模湿实验数据的闭环验证。

### 下一步发展方向
1.  **评价体系升级**：引入更多元的评分体系，如 AF3-iPTM, 分子动力学 (MD) 模拟筛选等。或者可以基于AI方法设计其他筛选方式并集成至该平台，实现分级，高通量筛选的固定pipeline范式。
2.  **效率优化**：基于 AlphaFold3 或其它端到端模型优化评分效率，或构建自动化的 MD 工作流。
3.  **模型扩展**：部署更多前沿生成模型，丰富生成和优化接口。
4.  **Agent 集成**：将接口对接 LLM Agent，实现全自动化的“生成-评估-优化”闭环迭代，由 Agent 自动制定筛选策略和优化方案。最终打造成“端到端”设计平台，输入自然语言，输出可对接湿实验的protein binders。
