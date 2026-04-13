# BCE Lab Report Pipeline

This pipeline orchestrates the generation of three types of blockchain research reports for BCE Lab projects:

- **Economic Reports** (econ): Market analysis, tokenomics, and economic metrics
- **Materials Reports** (mat): Whitepaper analysis, technical documentation review
- **Forensic Reports** (for): Security analysis, risk assessment, fraud detection

## Architecture

```
pipeline/
├── orchestrator.py          # Main entry point and report orchestration
├── monitor_forensic.py      # Daily forensic monitoring and escalation
├── translate.py             # Multi-language translation engine
├── config.py                # Configuration (languages, paths, naming)
├── gen_econ.py             # Economic report generator (external)
├── gen_mat.py              # Materials report generator (external)
├── gen_for.py              # Forensic report generator (external)
├── __init__.py             # Package initialization
└── README.md               # This file
```

## Quick Start

### 1. Generate a Single-Language Report

Generate an English economic report for Bitcoin v1:

```bash
python orchestrator.py --type econ --project btc --version 1 --lang en
```

### 2. Generate Multi-Language Reports

Generate reports in all 7 languages (English, Korean, French, Spanish, German, Japanese, Chinese):

```bash
python orchestrator.py --type econ --project eth --version 2 --lang all
```

### 3. Specify Custom Data File

```bash
python orchestrator.py --type mat --project sol --version 1 --lang ko --data /path/to/data.json
```

## Command-Line Arguments

### Required Arguments

| Argument | Options | Description |
|----------|---------|-------------|
| `--type` | `econ`, `mat`, `for` | Report type to generate |
| `--project` | any slug | Project identifier (e.g., btc, eth, sol) |
| `--version` | integer >= 1 | Report version number |
| `--lang` | language code or `all` | Target language(s) |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--data` | auto-detected | Path to project data JSON file |

## Supported Languages

The pipeline supports 7 languages with consistent terminology via the integrated glossary:

| Code | Language |
|------|----------|
| `en` | English |
| `ko` | Korean (한국어) |
| `fr` | French (Français) |
| `es` | Spanish (Español) |
| `de` | German (Deutsch) |
| `ja` | Japanese (日本語) |
| `zh` | Chinese (中文) |

## Output Files

Generated reports follow the naming convention:

```
{project_slug}_{report_type}_v{version}_{language}.pdf
```

### Examples

```
btc_econ_v1_en.pdf      # Bitcoin economic report, English
eth_mat_v2_ko.pdf       # Ethereum materials report, Korean
sol_for_v1_zh.pdf       # Solana forensic report, Chinese
```

All files are saved to the configured `OUTPUT_DIR` (see `config.py`).

## Forensic Monitoring

Run daily forensic monitoring for all tracked projects:

```bash
python monitor_forensic.py
```

Monitor specific projects:

```bash
python monitor_forensic.py --projects btc,eth,sol,bnb
```

### Forensic Triggers

The system monitors 5 forensic triggers (STR-002 §3.2):

1. **Price Volatility**: 24h price change >= ±15%
2. **Volume Anomaly**: Daily volume >= 300% of 7-day average
3. **Whale Movement**: Large transfers >= 1% of supply
4. **Exchange Inflow**: Net inflow to exchanges >= 0.5% of supply
5. **Insider Activity**: Abnormal movement from team/insider wallets

### Escalation Routing

- **0 flags**: Log only (INFO level)
- **1 flag**: Alert CRO team (WARNING level)
- **2+ flags**: Request forensic report (CRITICAL level)

Results are saved as JSON logs with timestamp and full details.

## Translation System

The pipeline includes multi-language support with consistent blockchain terminology.

### Key Components

- **`translate.py`**: Core translation engine with glossary support
- **`GLOSSARY`**: Blockchain terms in all 7 languages (120+ terms)
- **Text field detection**: Automatically identifies translatable content
- **Metadata preservation**: Maintains numeric values, dates, addresses

### Example Usage

```python
from translate import translate_all_languages

# Load project data (English)
project_data = load_project_data('btc.json')

# Generate translations for all languages
translations = translate_all_languages(project_data)

# Access specific translation
korean_data = translations['ko']
french_data = translations['fr']
```

## Configuration

Edit `config.py` to customize:

- Output directory path
- Supported languages
- Report file naming convention
- API keys and service endpoints

## Data Format

Project data should be provided as JSON with the following structure:

```json
{
  "name": "Bitcoin",
  "slug": "btc",
  "description": "Digital currency...",
  "market_cap": 1200000000000,
  "price": 45000.50,
  "analysis": {
    "econ": "Economic analysis...",
    "mat": "Materials analysis...",
    "for": "Forensic analysis..."
  },
  "metadata": {
    "created_at": "2024-01-01T00:00:00Z",
    "team": ["..."]
  }
}
```

## Error Handling

- **Missing data file**: Specify with `--data` or ensure default location is populated
- **Invalid language code**: Use `--lang all` or check supported languages
- **Generator errors**: Check logs for detailed error messages
- **API failures**: Monitor_forensic uses mock data; integrate real APIs as needed

## Logging

All components produce logs:

- **Orchestrator**: Console output with summary
- **Monitor_forensic**: `forensic_monitoring.log` + console output
- **Translate**: DEBUG level logging for translation operations
- **Generators**: Check individual generator documentation

## Performance

- Single report generation: ~10-30 seconds (varies by generator)
- Multi-language batch (7 languages): ~1-3 minutes
- Daily monitoring: <1 minute for 5 projects

## TODO / Future Enhancements

- [ ] Integrate real translation API (Google Translate, DeepL)
- [ ] Connect to CoinGecko API for live price/volume data
- [ ] Implement whale/insider tracking via blockchain indexer
- [ ] Add caching for translated glossary terms
- [ ] Implement report versioning and diff tracking
- [ ] Add email notifications for forensic escalations
- [ ] Create web dashboard for monitoring results

## Support

For issues or questions:
1. Check logs for error messages
2. Verify data file format and path
3. Ensure all dependencies are installed
4. Review this README for common patterns

## References

- STR-002 §3.2: Forensic monitoring requirements
- Process Documentation §4: Monitoring log format
- Process Documentation §3.5: Glossary management
