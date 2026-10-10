## Day 3 - Agent Reliability & Eval

### Reliability

- Added input validation
- Added tool router
- Added tool exception handling

### Eval

Cases:

- High risk → should call tool
- Low risk → should call tool
- AEB knowledge question → should not call tool
- Python question → should not call tool

Metric:

Tool Selection Accuracy