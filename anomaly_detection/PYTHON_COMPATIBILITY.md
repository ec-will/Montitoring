# Python 3.6 Compatibility

## Target Environment

- **jeffsc8 HPC Cluster**: Python 3.6.8
- **Local Development**: Python 3.8+

## Python 3.6 Limitations

The code has been updated to be compatible with Python 3.6.8:

### Changes Made

1. **No `datetime.fromisoformat()`** (added in Python 3.7)
   - Replaced with custom `parse_iso_datetime()` function
   - Uses `strptime()` with multiple format attempts

2. **No f-strings** in core detector
   - `detector.py` uses `.format()` instead
   - Python 3.6 supports f-strings, but staying consistent

3. **Type hints** are compatible
   - `from typing import` works in Python 3.6
   - All type hints preserved

### Files Status

- ✅ **detector.py** - Fully Python 3.6 compatible
- ✅ **fetch_data.sh** - Bash script (no Python version dependency)
- ✅ **Config files** - YAML (no Python version dependency)
- ⚠️ **alert_manager.py** - Contains f-strings (Python 3.6+)
- ⚠️ **train_model.py** - Contains f-strings (Python 3.6+)

### Note on F-Strings

F-strings were introduced in Python 3.6, so technically they work on jeffsc8. However, if you encounter issues, they can be easily converted to `.format()` style.

## Testing on jeffsc8

```bash
# SSH to jeffsc8
ssh jeffsc8

# Navigate to monitoring directory
cd /e/08/erthch01/monitoring/anomaly_detection

# Test Python version
python3 --version  # Should show 3.6.8

# Test detector
./detector.py --config config/detection_config.yaml --test
```

## Dependencies

All required packages work with Python 3.6:
- numpy >= 1.14.0 (Python 3.6 compatible)
- pyyaml >= 3.13 (Python 3.6 compatible)
- requests >= 2.18.0 (Python 3.6 compatible)
- scikit-learn >= 0.19.0 (Python 3.6 compatible, optional)
