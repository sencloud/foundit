import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from backtester import StockBacktester
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

def main():
    logger.info("启动回测系统Web界面")
    st.title("A股全市场回测系统")
    
    # Tushare Token输入
    ts_token = st.text_input("请输入Tushare Token:", type="password")
    
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
    if st.button("运行回测") and ts_token:
        logger.info(f"开始回测 - 开始日期: {start_date}, 结束日期: {end_date}")
        with st.spinner('正在运行回测...'):
            backtester = StockBacktester(ts_token)
            st.session_state.backtest_results = backtester.run_market_backtest(
                start_date=start_date,
                end_date=end_date
            )
            logger.info("回测完成")
            st.success('回测完成！')
    
    # 显示回测结果
    if st.session_state.backtest_results:
        logger.info("显示回测结果")
        # 创建tab
        tabs = st.tabs(["主板", "创业板", "科创板"])
        market_names = ['MAIN', 'GEM', 'STAR']
        
        for tab, market in zip(tabs, market_names):
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

if __name__ == "__main__":
    main() 