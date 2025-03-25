# A股全市场回测系统

这是一个基于Streamlit开发的A股全市场回测系统，使用Tushare获取数据，Backtrader进行回测，实现了基于均线交叉的交易策略。

## 功能特点

- 全市场股票回测：支持A股所有上市股票的回测
- 多市场分类：按主板、创业板、科创板分类展示结果
- 高收益筛选：只显示收益率超过50%的股票
- 详细交易记录：记录每笔交易的详细信息
- 可视化展示：使用Plotly绘制交易图表
- 完整日志系统：使用loguru记录系统运行日志

## 交易策略

### 开仓条件
1. 金叉信号：
   - 快线（5日均线）上穿慢线（20日均线）
   - 交叉幅度超过0.1%
   - 成交量大于7日均量的1.5倍
   - 成交量持续上升（3日）
   - 周趋势向上（5日均线斜率）

### 平仓条件
1. 死叉信号：快线下穿慢线
2. ATR止损：价格低于入场价-2倍ATR
3. ATR止盈：价格高于入场价+3倍ATR
4. 追踪止损：价格低于20日最高价

### 其他规则
- T+1交易规则
- 单次交易至少100股
- 使用95%可用资金
- 手续费0.03%

## 安装说明

1. 克隆代码库：
```bash
git clone https://github.com/sencloud/foundit.git
cd find_it
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 获取Tushare Token：
- 访问 https://tushare.pro
- 注册并登录
- 在个人中心获取token

## 使用方法

1. 启动应用：
```bash
streamlit run app.py
```

2. 在浏览器中打开应用（默认 http://localhost:8501）

3. 输入Tushare Token

4. 选择回测日期范围（默认2020年1月1日至今）

5. 点击"运行回测"按钮

6. 查看回测结果：
   - 按市场分类查看超过50%收益率的股票
![image](https://github.com/user-attachments/assets/576f36d4-b8ba-48a5-947a-0dd67d19eb72)


## 日志系统

系统使用loguru进行日志记录：
- 日志文件保存在 `logs` 目录
- 按天轮换日志文件
- 保留30天的历史日志
- 同时输出到控制台和文件
- 不同级别的日志使用不同颜色区分

## 依赖包

- streamlit==1.32.0
- tushare==1.2.89
- pandas==2.2.1
- numpy==1.26.4
- plotly==5.19.0
- backtrader==1.9.78.123
- loguru==0.7.2

## 注意事项

1. 需要有效的Tushare Token才能使用
2. 回测时间范围建议不要过长，以免数据量过大
3. 首次运行可能需要较长时间获取数据
4. 建议使用稳定的网络连接

## 系统架构

- `app.py`: Streamlit前端界面
- `backtester.py`: 回测引擎和数据获取
- `strategy.py`: 交易策略实现
- `logger_config.py`: 日志系统配置
- `requirements.txt`: 项目依赖

## 风险提示

本系统仅供学习和研究使用，不构成任何投资建议。使用本系统进行实盘交易需要自行承担风险。

## 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进这个项目。

## 许可证

MIT License
