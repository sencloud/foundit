import tushare as ts
import pandas as pd
import numpy as np
from loguru import logger
import time
from datetime import datetime
import os

class StockFinder:
    def __init__(self, ts_token):
        ts.set_token(ts_token)
        self.pro = ts.pro_api()
        self.api_calls = 0  # API调用计数
        self.last_reset = time.time()  # 上次重置计数的时间
        self.rate_limit = 290  # 每分钟API调用限制（留10个余量）
        self.cache_dir = "cache"  # 缓存目录
        self.ensure_cache_dir()
        
    def ensure_cache_dir(self):
        """确保缓存目录存在"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
    def get_cache_file_path(self, days):
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"inflow_stocks_{days}days.csv")
        
    def is_cache_valid(self, cache_file):
        """检查缓存是否有效（当天的缓存且包含所需字段）"""
        if not os.path.exists(cache_file):
            return False
        
        try:
            # 读取缓存文件
            df = pd.read_csv(cache_file)
            
            # 检查必需的字段是否存在
            required_fields = ['code', 'name', 'industry', 'total_inflow', 
                             'avg_daily_inflow', 'inflow_ratio', 'holders_decreased', 
                             'holder_change_desc']
            if not all(field in df.columns for field in required_fields):
                logger.info(f"缓存文件缺少必需字段，需要重新计算")
                return False
            
            # 获取文件最后修改时间
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            today = datetime.now()
            
            # 如果是当天的缓存则有效
            return (mtime.year == today.year and 
                    mtime.month == today.month and 
                    mtime.day == today.day)
                    
        except Exception as e:
            logger.error(f"读取缓存文件失败: {str(e)}")
            return False

    def update_cache_with_holder_info(self, df):
        """更新DataFrame中的股东人数信息"""
        logger.info("开始更新股东人数信息")
        total_stocks = len(df)
        updated_records = []
        
        for idx, row in df.iterrows():
            if idx % 50 == 0:
                logger.info(f"正在更新股东信息: {idx}/{total_stocks}")
                
            ts_code = row['code']
            # 获取股东人数变动情况
            holders_decreased, holder_change_desc = self._get_holder_number_change(ts_code)
            
            # 更新记录
            record = row.to_dict()
            record['holders_decreased'] = holders_decreased if holders_decreased is not None else False
            record['holder_change_desc'] = holder_change_desc if holder_change_desc else "无最新变动数据"
            updated_records.append(record)
            
        return pd.DataFrame(updated_records)

    def _check_rate_limit(self):
        """检查并控制API调用频率"""
        current_time = time.time()
        # 如果距离上次重置已经过了60秒，重置计数器
        if current_time - self.last_reset >= 60:
            logger.debug(f"重置API调用计数 - 上一分钟调用次数: {self.api_calls}")
            self.api_calls = 0
            self.last_reset = current_time
            
        # 如果当前分钟内的调用次数已达到限制
        if self.api_calls >= self.rate_limit:
            wait_time = 60 - (current_time - self.last_reset)
            if wait_time > 0:
                logger.warning(f"达到API调用限制，等待{wait_time:.1f}秒")
                time.sleep(wait_time)
                self.api_calls = 0
                self.last_reset = time.time()
        
        self.api_calls += 1
        
    def _get_all_stocks(self):
        """获取所有A股列表"""
        logger.info("开始获取A股列表")
        try:
            self._check_rate_limit()
            stocks = self.pro.stock_basic(
                exchange='',
                list_status='L',
                fields='ts_code,name,area,industry,market'
            )
            logger.info(f"成功获取{len(stocks)}只股票的基本信息")
            return stocks
        except Exception as e:
            logger.error(f"获取股票列表失败: {str(e)}")
            return pd.DataFrame()
    
    def _get_money_flow(self, ts_code, start_date, end_date):
        """获取个股资金流向数据"""
        try:
            self._check_rate_limit()
            logger.debug(f"获取{ts_code}的资金流向数据 ({start_date} to {end_date})")
            df = self.pro.moneyflow(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields='trade_date,buy_sm_vol,buy_sm_amount,sell_sm_vol,sell_sm_amount,buy_md_vol,buy_md_amount,sell_md_vol,sell_md_amount,buy_lg_vol,buy_lg_amount,sell_lg_vol,sell_lg_amount,buy_elg_vol,buy_elg_amount,sell_elg_vol,sell_elg_amount,net_mf_vol,net_mf_amount'
            )
            if not df.empty:
                logger.debug(f"{ts_code}: 成功获取{len(df)}天的资金流向数据")
            return df
        except Exception as e:
            logger.error(f"获取{ts_code}资金流向数据失败: {str(e)}")
            return None

    def _get_holder_number_change(self, ts_code):
        """获取最近两期股东人数变动情况"""
        try:
            self._check_rate_limit()
            # 获取最近的股东数据（默认按公告日期降序）
            df = self.pro.stk_holdernumber(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,holder_num'
            )
            
            if df is None or df.empty or len(df) < 2:
                return None, None
                
            # 获取最近两期的数据
            latest = df.iloc[0]
            previous = df.iloc[1]
            
            # 计算变动
            change = latest['holder_num'] - previous['holder_num']
            change_pct = (change / previous['holder_num']) * 100
            
            # 生成变动描述
            if change < 0:
                desc = f"减少{abs(change)}户({abs(change_pct):.2f}%)"
                is_decreased = True
            else:
                desc = f"增加{change}户({change_pct:.2f}%)"
                is_decreased = False
                
            # 添加日期信息
            desc = f"{latest['end_date']}较{previous['end_date']}: {desc}"
            
            return is_decreased, desc
                
        except Exception as e:
            logger.error(f"获取{ts_code}股东人数数据失败: {str(e)}")
            return None, None

    def analyze_stock_inflow(self, ts_code, name, industry, start_date, end_date):
        """分析单只股票的资金流入情况"""
        flow_data = self._get_money_flow(ts_code, start_date, end_date)
        if flow_data is None or flow_data.empty:
            return None
            
        # 计算大单和超大单的净流入
        flow_data['large_net_inflow'] = (
            (flow_data['buy_lg_amount'] + flow_data['buy_elg_amount']) -
            (flow_data['sell_lg_amount'] + flow_data['sell_elg_amount'])
        )
        
        # 统计指标
        total_days = len(flow_data)
        inflow_days = len(flow_data[flow_data['large_net_inflow'] > 0])
        total_inflow = flow_data['large_net_inflow'].sum()
        
        # 筛选条件
        if (inflow_days / total_days > 0.6) and (total_inflow > 0):
            avg_daily_inflow = total_inflow / total_days
            
            # 获取股东人数变动情况
            holders_decreased, holder_change_desc = self._get_holder_number_change(ts_code)
            
            return {
                'code': ts_code,
                'name': name,
                'industry': industry,
                'inflow_days': inflow_days,
                'total_days': total_days,
                'inflow_ratio': round(inflow_days / total_days * 100, 2),
                'total_inflow': round(total_inflow / 10000, 2),  # 转换为亿元
                'avg_daily_inflow': round(avg_daily_inflow / 10000, 2),  # 转换为亿元
                'holders_decreased': holders_decreased if holders_decreased is not None else False,
                'holder_change_desc': holder_change_desc if holder_change_desc else "无最新变动数据",
                'reason': f"近{total_days}天资金净流入{inflow_days}天，累计净流入{round(total_inflow/10000, 2)}亿元"
            }
        return None

    def find_continuous_inflow_stocks(self, days=60, use_cache=True, base_stocks=None):
        """
        寻找持续资金流入的股票
        
        Args:
            days: 分析的天数
            use_cache: 是否使用缓存
            base_stocks: 基础股票列表，如果提供则只分析这些股票
        """
        logger.info(f"开始寻找资金持续流入的股票 (分析周期: {days}天)")
        
        cache_file = self.get_cache_file_path(days)
        
        # 检查缓存
        if use_cache and os.path.exists(cache_file):
            logger.info(f"发现缓存文件: {cache_file}")
            df = pd.read_csv(cache_file)
            
            # 检查是否需要更新股东信息
            if not all(field in df.columns for field in ['holders_decreased', 'holder_change_desc']):
                logger.info("缓存文件缺少股东信息字段，开始更新...")
                df = self.update_cache_with_holder_info(df)
                # 保存更新后的缓存
                df.to_csv(cache_file, index=False)
                logger.info("股东信息更新完成，已保存到缓存")
            elif not self.is_cache_valid(cache_file):
                logger.info("缓存文件已过期，需要重新计算")
                df = None
            else:
                logger.info("使用有效的缓存数据")
                return df
                
            if df is not None:
                return df
            
        # 获取当前日期
        today = pd.Timestamp.now()
        end_date = today.strftime('%Y%m%d')
        start_date = (today - pd.Timedelta(days=days)).strftime('%Y%m%d')
        logger.info(f"分析时间范围: {start_date} 至 {end_date}")
        
        # 获取待分析的股票列表
        if base_stocks is None:
            stocks = self._get_all_stocks()
            if stocks.empty:
                logger.error("获取股票列表失败，退出查找")
                return pd.DataFrame()
        else:
            stocks = base_stocks
            
        results = []
        total_stocks = len(stocks)
        processed_stocks = 0
        
        logger.info(f"开始处理{total_stocks}只股票的资金流向数据")
        start_time = time.time()
        
        for _, stock in stocks.iterrows():
            ts_code = stock['ts_code'] if 'ts_code' in stock else stock['code']
            name = stock['name']
            industry = stock['industry']
            processed_stocks += 1
            
            if processed_stocks % 50 == 0:
                elapsed_time = time.time() - start_time
                avg_time_per_stock = elapsed_time / processed_stocks
                remaining_stocks = total_stocks - processed_stocks
                estimated_remaining_time = remaining_stocks * avg_time_per_stock
                logger.info(f"进度: {processed_stocks}/{total_stocks} ({processed_stocks/total_stocks*100:.1f}%) "
                          f"预计还需: {estimated_remaining_time/60:.1f}分钟")
            
            # 分析股票
            result = self.analyze_stock_inflow(
                ts_code, name, industry,
                start_date, end_date
            )
            
            if result:
                results.append(result)
                logger.info(f"找到符合条件的股票: {ts_code} {name} - "
                          f"净流入{result['inflow_days']}/{result['total_days']}天, "
                          f"累计净流入{result['total_inflow']}亿元")
                
        # 转换结果为DataFrame
        if results:
            df_results = pd.DataFrame(results)
            
            # 保存缓存
            if use_cache:
                df_results.to_csv(cache_file, index=False)
                logger.info(f"结果已缓存到: {cache_file}")
        else:
            df_results = pd.DataFrame()
            
        total_time = time.time() - start_time
        logger.info(f"找股完成，耗时{total_time/60:.1f}分钟，找到{len(results)}只符合条件的股票")
        return df_results

    def find_stocks(self, strategy="资金持续流入"):
        """
        根据不同策略寻找股票
        """
        logger.info(f"执行找股策略: {strategy}")
        if strategy == "资金持续流入":
            # 首先获取60天的基础股票池
            base_stocks = self.find_continuous_inflow_stocks(days=60)
            if base_stocks.empty:
                logger.warning("未找到符合60天条件的股票")
                return []
                
            # 对基础股票池进行多周期分析
            periods = [10, 20, 90, 180]
            results = {}
            
            for days in periods:
                logger.info(f"开始分析{days}天周期")
                period_results = self.find_continuous_inflow_stocks(
                    days=days,
                    base_stocks=base_stocks
                )
                if not period_results.empty:
                    results[days] = period_results
                    
            return results
        else:
            logger.warning(f"未实现的策略: {strategy}")
            return [] 