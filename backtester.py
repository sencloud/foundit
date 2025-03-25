import backtrader as bt
import pandas as pd
import tushare as ts
from datetime import datetime
from strategy import MAStrategy
from loguru import logger

class StockBacktester:
    def __init__(self, ts_token):
        logger.info("初始化回测系统")
        ts.set_token(ts_token)
        self.pro = ts.pro_api()
        
    def get_stock_list(self):
        """获取A股所有股票列表"""
        logger.info("获取A股股票列表")
        stocks = self.pro.stock_basic(exchange='', list_status='L', 
                                    fields='ts_code,symbol,name,area,industry,market')
        logger.info(f"获取到 {len(stocks)} 只股票")
        return stocks
        
    def get_stock_data(self, ts_code, start_date, end_date):
        """获取单个股票的历史数据"""
        try:
            logger.debug(f"获取股票 {ts_code} 的历史数据 - 开始日期: {start_date}, 结束日期: {end_date}")
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df.empty:
                logger.warning(f"股票 {ts_code} 没有数据")
                return None
                
            # 按日期升序排序
            df = df.sort_values('trade_date')
            
            # 转换为backtrader可用的格式
            df['datetime'] = pd.to_datetime(df['trade_date'])
            df.set_index('datetime', inplace=True)
            df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'vol': 'volume',
            }, inplace=True)
            
            logger.debug(f"股票 {ts_code} 数据获取成功 - 数据条数: {len(df)}")
            return df
            
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 数据失败: {str(e)}")
            return None
            
    def run_backtest(self, stock_data, initial_cash=100000.0):
        """运行单个股票的回测"""
        logger.info(f"开始回测 - 初始资金: {initial_cash:.2f}")
        cerebro = bt.Cerebro()
        
        # 添加数据
        data = bt.feeds.PandasData(dataname=stock_data)
        cerebro.adddata(data)
        
        # 设置初始资金
        cerebro.broker.setcash(initial_cash)
        
        # 设置手续费
        cerebro.broker.setcommission(commission=0.0003)  # 0.03%
        
        # 添加策略
        cerebro.addstrategy(MAStrategy)
        
        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='returns')
        
        # 运行回测
        logger.debug("开始执行回测策略")
        results = cerebro.run()
        strategy = results[0]
        
        # 获取回测结果
        final_value = cerebro.broker.getvalue()
        pnl = final_value - initial_cash
        return_pct = (final_value / initial_cash - 1) * 100
        
        # 获取收益曲线数据
        returns = strategy.analyzers.returns.get_analysis()
        equity_curve = pd.Series(returns).cumsum()
        equity_curve = (1 + equity_curve) * initial_cash
        
        logger.info(f"回测完成 - 最终资金: {final_value:.2f}, 盈亏: {pnl:.2f}, 收益率: {return_pct:.2f}%")
        return {
            'initial_cash': initial_cash,
            'final_value': final_value,
            'pnl': pnl,
            'return_pct': return_pct,
            'trades': strategy.trades,
            'equity_curve': equity_curve
        }
        
    def run_single_stock_backtest(self, stock_code, start_date, end_date, initial_cash=100000.0):
        """运行单个股票的回测"""
        logger.info(f"开始单股回测 - 股票代码: {stock_code}")
        
        try:
            # 获取股票信息
            stock_info = self.pro.stock_basic(ts_code=stock_code, fields='ts_code,symbol,name,area,industry,market').iloc[0]
            
            # 获取股票数据
            data = self.get_stock_data(stock_code, start_date, end_date)
            if data is None:
                logger.error(f"获取股票 {stock_code} 数据失败")
                return None
                
            # 运行回测
            result = self.run_backtest(data, initial_cash)
            result['stock_info'] = stock_info.to_dict()
            
            return result
            
        except Exception as e:
            logger.error(f"单股回测失败: {str(e)}")
            return None
        
    def run_market_backtest(self, start_date='20200101', end_date=None):
        """运行全市场回测"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
            
        logger.info(f"开始全市场回测 - 开始日期: {start_date}, 结束日期: {end_date}")
        
        # 获取股票列表
        stocks = self.get_stock_list()
        results = {}
        
        # 按市场分类
        markets = {
            'MAIN': [],  # 主板
            'GEM': [],   # 创业板
            'STAR': [],  # 科创板
        }
        
        # 遍历每只股票进行回测
        total_stocks = len(stocks)
        for idx, (_, stock) in enumerate(stocks.iterrows(), 1):
            try:
                logger.info(f"正在回测第 {idx}/{total_stocks} 只股票: {stock['ts_code']} ({stock['name']})")
                data = self.get_stock_data(stock['ts_code'], start_date, end_date)
                if data is not None:
                    result = self.run_backtest(data)
                    result['stock_info'] = stock.to_dict()
                    
                    # 根据市场分类存储结果
                    if stock['market'] in ['主板', '中小板']:
                        markets['MAIN'].append(result)
                        logger.debug(f"股票 {stock['ts_code']} 分类为主板")
                    elif stock['market'] == '创业板':
                        markets['GEM'].append(result)
                        logger.debug(f"股票 {stock['ts_code']} 分类为创业板")
                    elif stock['market'] == '科创板':
                        markets['STAR'].append(result)
                        logger.debug(f"股票 {stock['ts_code']} 分类为科创板")
                        
            except Exception as e:
                logger.error(f"回测股票 {stock['ts_code']} 失败: {str(e)}")
                continue
                
        # 输出回测统计信息
        for market, results in markets.items():
            if results:
                avg_return = sum(r['return_pct'] for r in results) / len(results)
                profit_count = len([r for r in results if r['pnl'] > 0])
                logger.info(f"{market}市场回测统计:")
                logger.info(f"- 股票数量: {len(results)}")
                logger.info(f"- 平均收益率: {avg_return:.2f}%")
                logger.info(f"- 盈利股票数: {profit_count}")
                logger.info(f"- 亏损股票数: {len(results) - profit_count}")
                
        return markets 