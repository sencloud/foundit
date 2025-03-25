import backtrader as bt
from loguru import logger

class MAStrategy(bt.Strategy):
    params = (
        ('fast_period', 5),
        ('slow_period', 20),
        ('volume_ratio_threshold', 1.5),
        ('crossover_threshold', 0.001),
        ('atr_period', 14),
        ('atr_loss_multiplier', 2.0),
        ('atr_profit_multiplier', 3.0),
        ('enable_trailing_stop', False),
        ('margin_ratio', 0.95),
    )

    def __init__(self):
        logger.debug(f"初始化策略 - 快线周期: {self.p.fast_period}, 慢线周期: {self.p.slow_period}")
        self.fast_ma = bt.indicators.SMA(period=self.p.fast_period)
        self.slow_ma = bt.indicators.SMA(period=self.p.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
        self.atr = bt.indicators.ATR(period=self.p.atr_period)
        
        # 追踪止损
        self.trailing_stop = bt.indicators.Highest(self.data.close, period=20)
        
        # 记录交易信息
        self.trade_reason = ""
        self.entry_price = 0
        self.buy_dates = set()
        self.trades = []

    def calculate_trade_size(self, price):
        cash = self.broker.getcash()
        shares = int((cash * self.p.margin_ratio) / price / 100) * 100
        logger.debug(f"计算交易数量 - 当前资金: {cash:.2f}, 目标价格: {price:.2f}, 计算得到: {shares}股")
        return shares

    def next(self):
        current_price = self.data.close[0]
        current_date = self.data.datetime.date()

        if not self.position:  # 没有持仓
            # 金叉判定
            crossover_occurred = (self.fast_ma[0] > self.slow_ma[0] and 
                                self.fast_ma[-1] <= self.slow_ma[-1])
            
            if crossover_occurred:
                logger.debug(f"检测到金叉 - 日期: {current_date}, 快线: {self.fast_ma[0]:.2f}, 慢线: {self.slow_ma[0]:.2f}")
            
            # 交叉幅度计算
            crossover_pct = 0
            if crossover_occurred:
                denominator = (self.fast_ma[0] - self.fast_ma[-1]) - (self.slow_ma[0] - self.slow_ma[-1])
                if denominator != 0:
                    alpha = (self.slow_ma[-1] - self.fast_ma[-1]) / denominator
                    crossover_price = self.fast_ma[-1] + alpha*(self.fast_ma[0]-self.fast_ma[-1])
                    crossover_pct = abs(crossover_price - self.slow_ma[0])/self.slow_ma[0]
                    logger.debug(f"计算交叉幅度 - 交叉价格: {crossover_price:.2f}, 幅度: {crossover_pct:.4%}")

            if crossover_occurred:
                # 成交量条件
                current_volume = self.data.volume[0]
                prev_volume = sum([self.data.volume[-i] for i in range(1, 8)]) / 7
                volume_condition = current_volume > self.p.volume_ratio_threshold * prev_volume
                
                # 周趋势
                weekly_trend = self.fast_ma[0] > self.fast_ma[-5]
                
                # 成交量上升趋势
                volume_uptrend = (self.data.volume[0] > self.data.volume[-1] and 
                                self.data.volume[-1] > self.data.volume[-2])
                
                logger.debug(f"交易条件检查 - 日期: {current_date}")
                logger.debug(f"- 成交量条件: {volume_condition} (当前: {current_volume:.0f}, 均量: {prev_volume:.0f})")
                logger.debug(f"- 周趋势: {weekly_trend}")
                logger.debug(f"- 成交量上升: {volume_uptrend}")
                
                if (crossover_pct >= self.p.crossover_threshold and
                    volume_condition and volume_uptrend and weekly_trend):
                    
                    shares = self.calculate_trade_size(current_price)
                    
                    if shares >= 100:
                        self.trade_reason = (
                            f"金叉信号 - 交叉幅度: {crossover_pct:.4%}, "
                            f"量能比: {current_volume/prev_volume:.2f}"
                        )
                        logger.info(f"触发买入信号 - {self.trade_reason}")
                        self.order = self.buy(size=shares)
                        if self.order:
                            self.buy_dates.add(current_date)
                            self.entry_price = current_price
                            
                            # 记录交易
                            self.trades.append({
                                'date': current_date,
                                'type': 'BUY',
                                'price': current_price,
                                'size': shares,
                                'reason': self.trade_reason
                            })
                            logger.info(f"买入执行成功 - 价格: {current_price:.2f}, 数量: {shares}")
                    else:
                        logger.warning(f"计算得到的交易数量不足100股: {shares}")
                else:
                    logger.debug("交易条件不满足，跳过买入")
        
        else:  # 有持仓
            # T+1规则检查
            if current_date in self.buy_dates:
                logger.debug(f"T+1规则限制，跳过交易 - 日期: {current_date}")
                return
                
            # ATR止盈止损价格
            current_atr = self.atr[0]
            stop_loss = self.entry_price - (current_atr * self.p.atr_loss_multiplier)
            take_profit = self.entry_price + (current_atr * self.p.atr_profit_multiplier)
            
            logger.debug(f"持仓检查 - 日期: {current_date}")
            logger.debug(f"- 当前价格: {current_price:.2f}")
            logger.debug(f"- ATR: {current_atr:.2f}")
            logger.debug(f"- 止损价: {stop_loss:.2f}")
            logger.debug(f"- 止盈价: {take_profit:.2f}")
            
            # 死叉检查
            if self.crossover < 0:
                self.trade_reason = "死叉信号"
                logger.info(f"触发死叉卖出信号 - 日期: {current_date}")
                self.order = self.close()
                if self.order:
                    self.trades.append({
                        'date': current_date,
                        'type': 'SELL',
                        'price': current_price,
                        'size': self.position.size,
                        'reason': self.trade_reason
                    })
                    logger.info(f"死叉卖出执行成功 - 价格: {current_price:.2f}, 数量: {self.position.size}")
            
            # ATR止损检查
            elif current_price < stop_loss:
                self.trade_reason = f"ATR止损 (止损价: {stop_loss:.4f})"
                logger.info(f"触发ATR止损信号 - {self.trade_reason}")
                self.order = self.close()
                if self.order:
                    self.trades.append({
                        'date': current_date,
                        'type': 'SELL',
                        'price': current_price,
                        'size': self.position.size,
                        'reason': self.trade_reason
                    })
                    logger.info(f"ATR止损执行成功 - 价格: {current_price:.2f}, 数量: {self.position.size}")
            
            # ATR止盈检查
            elif current_price > take_profit:
                self.trade_reason = f"ATR止盈 (止盈价: {take_profit:.4f})"
                logger.info(f"触发ATR止盈信号 - {self.trade_reason}")
                self.order = self.close()
                if self.order:
                    self.trades.append({
                        'date': current_date,
                        'type': 'SELL',
                        'price': current_price,
                        'size': self.position.size,
                        'reason': self.trade_reason
                    })
                    logger.info(f"ATR止盈执行成功 - 价格: {current_price:.2f}, 数量: {self.position.size}")
            
            # 追踪止损检查
            elif self.p.enable_trailing_stop and current_price < self.trailing_stop[0]:
                self.trade_reason = f"追踪止损 (止损价: {self.trailing_stop[0]:.4f})"
                logger.info(f"触发追踪止损信号 - {self.trade_reason}")
                self.order = self.close()
                if self.order:
                    self.trades.append({
                        'date': current_date,
                        'type': 'SELL',
                        'price': current_price,
                        'size': self.position.size,
                        'reason': self.trade_reason
                    })
                    logger.info(f"追踪止损执行成功 - 价格: {current_price:.2f}, 数量: {self.position.size}") 