import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from backtester import StockBacktester
from foundit import StockFinder
from loguru import logger
import logger_config  # 导入日志配置

# 页面配置
st.set_page_config(
    page_title="A股全市场回测系统",
    page_icon="📈",
    layout="wide"
)

# 初始化session state
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'single_stock_result' not in st.session_state:
    st.session_state.single_stock_result = None
if 'stock_discovery_results' not in st.session_state:
    st.session_state.stock_discovery_results = None

def main():
    logger.info("启动回测系统Web界面")
    st.title("A股全市场回测系统")
    
    # 创建主要tab
    main_tabs = st.tabs(["全市场回测", "单股回测", "找股"])
    
    with main_tabs[0]:  # 全市场回测tab
        # Tushare Token输入
        ts_token = st.text_input("请输入Tushare Token:", type="password", key="market_token")
        
        # 日期选择
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "开始日期",
                datetime(2020, 1, 1)
            ).strftime("%Y%m%d")
        with col2:
            end_date = st.date_input(
                "结束日期",
                datetime.now()
            ).strftime("%Y%m%d")
        
        # 运行回测按钮
        if st.button("运行回测", key="market_backtest") and ts_token:
            logger.info(f"开始全市场回测 - 开始日期: {start_date}, 结束日期: {end_date}")
            with st.spinner('正在运行回测...'):
                backtester = StockBacktester(ts_token)
                st.session_state.backtest_results = backtester.run_market_backtest(
                    start_date=start_date,
                    end_date=end_date
                )
                logger.info("全市场回测完成")
                st.success('回测完成！')
        
        # 显示回测结果
        if st.session_state.backtest_results:
            logger.info("显示全市场回测结果")
            # 创建tab
            market_tabs = st.tabs(["主板", "创业板", "科创板"])
            market_names = ['MAIN', 'GEM', 'STAR']
            
            for tab, market in zip(market_tabs, market_names):
                with tab:
                    results = st.session_state.backtest_results[market]
                    if not results:
                        logger.warning(f"没有{market}的回测结果")
                        st.warning(f"没有{market}的回测结果")
                        continue
                    
                    # 转换为DataFrame以便显示
                    df = pd.DataFrame([
                        {
                            '股票代码': r['stock_info']['ts_code'],
                            '股票名称': r['stock_info']['name'],
                            '初始资金': r['initial_cash'],
                            '最终价值': r['final_value'],
                            '盈亏': r['pnl'],
                            '收益率(%)': r['return_pct'],
                            '交易次数': len(r['trades'])
                        }
                        for r in results
                    ])
                    
                    # 筛选收益率大于50%的股票
                    df_high_return = df[df['收益率(%)'] > 50].copy()
                    
                    if len(df_high_return) == 0:
                        logger.info(f"{market}市场没有收益率超过50%的股票")
                        st.info(f"{market}市场没有收益率超过50%的股票")
                        continue
                    
                    # 显示汇总统计
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        avg_return = df_high_return['收益率(%)'].mean()
                        st.metric("平均收益率", f"{avg_return:.2f}%")
                        logger.debug(f"{market}市场高收益股票平均收益率: {avg_return:.2f}%")
                    with col2:
                        profit_count = len(df_high_return[df_high_return['盈亏'] > 0])
                        st.metric("盈利股票数", profit_count)
                        logger.debug(f"{market}市场高收益股票盈利数量: {profit_count}")
                    with col3:
                        loss_count = len(df_high_return[df_high_return['盈亏'] <= 0])
                        st.metric("亏损股票数", loss_count)
                        logger.debug(f"{market}市场高收益股票亏损数量: {loss_count}")
                    
                    # 显示详细结果表格
                    st.dataframe(df_high_return.sort_values('收益率(%)', ascending=False))
    
    with main_tabs[1]:  # 单股回测tab
        # Tushare Token输入
        ts_token_single = st.text_input("请输入Tushare Token:", type="password", key="single_token")
        
        # 股票代码输入
        stock_code = st.text_input("请输入股票代码（例如：000001.SZ）：")
        
        # 日期选择
        col1, col2 = st.columns(2)
        with col1:
            start_date_single = st.date_input(
                "开始日期",
                datetime(2020, 1, 1),
                key="single_start_date"
            ).strftime("%Y%m%d")
        with col2:
            end_date_single = st.date_input(
                "结束日期",
                datetime.now(),
                key="single_end_date"
            ).strftime("%Y%m%d")
        
        # 运行回测按钮
        if st.button("运行回测", key="single_backtest") and ts_token_single and stock_code:
            logger.info(f"开始单股回测 - 股票: {stock_code}, 开始日期: {start_date_single}, 结束日期: {end_date_single}")
            with st.spinner('正在运行回测...'):
                backtester = StockBacktester(ts_token_single)
                result = backtester.run_single_stock_backtest(
                    stock_code=stock_code,
                    start_date=start_date_single,
                    end_date=end_date_single
                )
                if result:
                    st.session_state.single_stock_result = result
                    logger.info("单股回测完成")
                    st.success('回测完成！')
                else:
                    logger.warning("单股回测失败")
                    st.error('回测失败，请检查股票代码是否正确')
        
        # 显示单股回测结果
        if st.session_state.single_stock_result:
            result = st.session_state.single_stock_result
            
            # 显示基本信息
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("股票名称", result['stock_info']['name'])
            with col2:
                st.metric("最终收益率", f"{result['return_pct']:.2f}%")
            with col3:
                st.metric("盈亏金额", f"{result['pnl']:.2f}")
            with col4:
                st.metric("交易次数", len(result['trades']))
            
            # 显示交易记录
            if result['trades']:
                st.subheader("交易记录")
                trades_df = pd.DataFrame(result['trades'])
                trades_df['date'] = pd.to_datetime(trades_df['date'])
                st.dataframe(trades_df)
                
                # 绘制收益曲线
                if 'equity_curve' in result:
                    st.subheader("收益曲线")
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=pd.to_datetime(result['equity_curve'].index),
                        y=result['equity_curve'].values,
                        mode='lines',
                        name='收益曲线'
                    ))
                    fig.update_layout(
                        title="策略收益曲线",
                        xaxis_title="日期",
                        yaxis_title="账户价值",
                        showlegend=True
                    )
                    st.plotly_chart(fig, use_container_width=True)

    with main_tabs[2]:  # 找股tab
        # Tushare Token输入
        ts_token_discovery = st.text_input("请输入Tushare Token:", type="password", key="discovery_token")
        
        # 策略说明
        st.markdown("""
        ### 策略说明
        
        #### 资金持续流入
        - 第一步：筛选最近60天资金持续流入的股票作为基础股票池
          1. 净流入天数超过总交易天数的60%
          2. 资金净流入总额为正
        - 第二步：对基础股票池进行多周期分析（5天、10天、90天、180天）
        - 结果按资金净流入金额从高到低排序
        - 使用缓存加速（当天有效）
        
        #### 突破新高（开发中）
        - 即将推出
        
        #### 量价齐升（开发中）
        - 即将推出
        
        #### 机构重仓（开发中）
        - 即将推出
        """)
        
        # 找股策略选择
        strategy = st.selectbox(
            "选择找股策略",
            ["资金持续流入", "突破新高", "量价齐升", "机构重仓"],
            index=0
        )
        
        # 运行找股按钮
        if st.button("开始找股", key="discover_stocks") and ts_token_discovery:
            logger.info(f"开始找股 - 策略: {strategy}")
            with st.spinner('正在寻找符合条件的股票...'):
                finder = StockFinder(ts_token_discovery)
                st.session_state.stock_discovery_results = finder.find_stocks(strategy)
                logger.info("找股完成")
                st.success('找股完成！')
        
        # 显示找股结果
        if st.session_state.stock_discovery_results:
            logger.info("显示找股结果")
            
            if isinstance(st.session_state.stock_discovery_results, dict):
                # 创建不同周期的tab
                period_tabs = st.tabs([f"{days}天" for days in sorted(st.session_state.stock_discovery_results.keys())])
                
                for tab, (days, df) in zip(period_tabs, sorted(st.session_state.stock_discovery_results.items())):
                    with tab:
                        # 显示结果统计
                        st.metric(f"{days}天资金持续流入股票数量", len(df))
                        
                        # 按资金流入总额排序并显示详细结果表格
                        if not df.empty and 'total_inflow' in df.columns:
                            df_sorted = df.sort_values('total_inflow', ascending=False)
                            st.dataframe(df_sorted)
            else:
                # 显示结果统计
                st.metric("找到的股票数量", len(df))
                
                # 按资金流入总额排序并显示详细结果表格
                if not df.empty and 'total_inflow' in df.columns:
                    df_sorted = df.sort_values('total_inflow', ascending=False)
                    st.dataframe(df_sorted)
                else:
                    st.dataframe(df)

if __name__ == "__main__":
    main() 