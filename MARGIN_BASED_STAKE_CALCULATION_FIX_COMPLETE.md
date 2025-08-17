# Margin-Based Stake Calculation Fix - COMPLETE

## Problem Statement

The real trading engine was configured for $200 per trade in the config, but it wasn't using that as the actual margin when opening positions on the exchange. The issue was that `stake_usd` was being treated as the notional amount rather than the margin amount.

### Original Issue
- Config: `stake_usd: 200`
- Quantity calculation: `qty = stake_usd / entry_price`
- With 3x leverage, actual margin = `200 / 3 = ~$66.67`
- **Problem**: The system treated `stake_usd` as notional value, not margin

### Desired Behavior
- `stake_usd` should represent the actual margin you want to risk
- With `stake_usd: 100` and 10x leverage:
  - Margin: $100 (what you actually risk)
  - Notional: $1,000 (100 × 10)
  - Quantity: $1,000 / entry_price

## Solution Implemented

### 1. Configuration Updates (`config/config.yaml`)

**Added new parameters:**
```yaml
real_trading:
  stake_usd: 100.0           # $100 capital per position (margin)
  stake_mode: MARGIN         # interpret stake as margin, not notional
  margin_mode: ISOLATED      # use isolated margin for safety
  default_leverage: 10       # Default 10x leverage
  max_leverage: 20           # Maximum 20x leverage cap

paper_trading:
  stake_amount: 100.0        # Match real trading capital
```

### 2. Real Trading Engine Updates (`src/trading/real_trading_engine.py`)

**Added new configuration parameters in `__init__`:**
```python
self.stake_usd = float(self.cfg.get("stake_usd", 100.0))  # $100 capital per position
self.stake_mode = str(self.cfg.get("stake_mode", "NOTIONAL")).upper()  # NOTIONAL | MARGIN
self.margin_mode = str(self.cfg.get("margin_mode", "ISOLATED")).upper()  # ISOLATED | CROSS
self.default_leverage = float(self.cfg.get("default_leverage", 10))  # Default 10x leverage
```

**Updated quantity calculation logic:**
```python
# Compute target notional from stake mode
if self.stake_mode == "MARGIN":
    notional_target = self.stake_usd * leverage   # capital × leverage
    logger.info(f"💰 MARGIN mode: ${self.stake_usd} capital × {leverage}x = ${notional_target:.2f} notional")
else:
    notional_target = self.stake_usd              # backwards-compatible (treat stake as size)
    logger.info(f"💰 NOTIONAL mode: ${self.stake_usd} notional (legacy)")

# Convert notional to quantity and round
qty = max(notional_target / entry_hint, step_size)
qty = self._round_step(qty, step_size)
```

**Enhanced status reporting:**
```python
'stake_usd': self.stake_usd,
'stake_mode': self.stake_mode,
'margin_mode': self.margin_mode,
'default_leverage': self.default_leverage,
```

## Key Features

### 1. **Flexible Stake Mode**
- `MARGIN` mode: `stake_usd` represents actual margin (recommended)
- `NOTIONAL` mode: `stake_usd` represents notional value (legacy compatibility)

### 2. **Proper Binance Futures Math**
- **Size/Notional (USDT)** = qty × price
- **Capital/Margin used (USDT)** = Size ÷ Leverage
- With MARGIN mode: Margin = stake_usd, Notional = stake_usd × leverage

### 3. **Safety Features**
- `ISOLATED` margin mode by default for safety
- Configurable leverage limits (default 10x, max 20x)
- Backward compatibility with existing configurations

### 4. **Consistency**
- Paper trading and real trading now both use $100 capital per position
- Same risk management approach across both systems

## Test Results

All tests passed successfully:

```
🚀 Testing Margin-Based Stake Calculation Fix
==================================================
✅ Configuration loading test passed!
✅ Engine initialization test passed!
✅ Margin calculation logic test passed!
✅ Binance futures margin calculation correct!
✅ Status reporting test passed!

📊 Test Results: 5/5 tests passed
🎉 All tests passed! Margin-based stake calculation is working correctly.
```

### Test Scenarios Verified

1. **Configuration Loading**: New parameters loaded correctly
2. **Engine Initialization**: RealTradingEngine initializes with correct values
3. **MARGIN Mode**: `notional = stake_usd × leverage` (100 × 10 = 1000)
4. **NOTIONAL Mode**: `notional = stake_usd` (legacy behavior)
5. **Binance Calculation**: Margin = (qty × price) ÷ leverage = $100 ✓
6. **Status Reporting**: New parameters included in API responses

## Example Usage

### With MARGIN Mode (Recommended)
```yaml
real_trading:
  stake_usd: 100.0      # $100 margin per position
  stake_mode: MARGIN    # Treat stake as margin
  default_leverage: 10  # 10x leverage
```

**Result:**
- Margin used: $100
- Notional value: $1,000
- Quantity: $1,000 / entry_price

### With NOTIONAL Mode (Legacy)
```yaml
real_trading:
  stake_usd: 100.0      # $100 notional per position
  stake_mode: NOTIONAL  # Treat stake as notional (legacy)
  default_leverage: 10  # Leverage ignored for sizing
```

**Result:**
- Notional value: $100
- Margin used: $100 / leverage = $10
- Quantity: $100 / entry_price

## Benefits

1. **Accurate Capital Allocation**: `stake_usd` now represents actual margin risked
2. **Predictable Risk Management**: Know exactly how much capital each trade uses
3. **Binance Compatibility**: Calculations match Binance futures margin requirements
4. **Backward Compatibility**: Existing configs still work with NOTIONAL mode
5. **Enhanced Observability**: New parameters visible in status reporting
6. **Safety First**: ISOLATED margin mode prevents cross-margin risks

## Files Modified

1. `config/config.yaml` - Updated configuration parameters
2. `src/trading/real_trading_engine.py` - Implemented margin-based calculation
3. `test_margin_based_stake_calculation.py` - Comprehensive test suite

## Deployment Notes

- **No breaking changes**: Existing configurations will default to NOTIONAL mode
- **Recommended**: Update to MARGIN mode for accurate capital allocation
- **Testing**: Run `python test_margin_based_stake_calculation.py` to verify
- **Monitoring**: Check status API for new configuration parameters

---

**Status**: ✅ COMPLETE  
**Date**: 2025-08-17  
**Tested**: All tests passing  
**Ready for Production**: Yes
