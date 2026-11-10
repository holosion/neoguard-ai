from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph
from pathlib import Path
path=Path(r'C:/Users/AKENA/Desktop/neonatal/output/word/NeoGuard_final_report_structured.docx')
doc=Document(path)
def remove_paragraph(p):
    el=p._element; el.getparent().remove(el)
start=None
for i,p in enumerate(doc.paragraphs):
    if p.text.strip()=='CHAPTER 6 ADDENDUM: VERIFIED AI TRAINING RESULTS': start=i; break
if start is not None:
    for p in list(doc.paragraphs[start:]): remove_paragraph(p)
target=next((p for p in doc.paragraphs if p.text.strip()=='6.15 Evaluation of the AI Objective'),None)
if target is None: raise SystemExit('6.15 heading not found')
items=[('CHAPTER 6.16: VERIFIED AI TRAINING RESULTS',1),('Workspace evidence recorded 480 synthetic sessions with 60 sessions in each of eight scenarios: normal, cooling, desaturation, combined, recovery, artifact, near-threshold and dropout. The split contained 288 training, 96 validation and 96 test sessions. The test set contained 19,272 rows and 5,375 positive rows. The deployed model used 12 causal features: last value, mean, slope per minute and standard deviation for temperature, SpO2 and heart rate. Its decision threshold was 0.75, with a 120-second feature window and 120-second label horizon.',0),('The synthetic test confusion matrix was TN=13,605, FP=292, FN=980 and TP=4,395. Precision was 0.9377, recall/sensitivity was 0.8177, average precision was 0.9475, ROC-AUC was 0.9748 and Brier score was 0.0476. At event level, 44 of 49 events were detected at onset, event sensitivity was 0.8980, warning-episode precision was 0.7361, false-warning episodes were 38 over 26.7667 monitoring hours, false-warning episodes were 1.4197 per hour, and median lead time among detected events was 107.5 seconds.',0),('The threshold-only baseline had precision 0.9940, recall 0.7669, ROC-AUC 0.8825 and Brier score 0.0663. It detected 25 of 49 events at onset, with event sensitivity 0.5102, warning-episode precision 0.8077, 20 false-warning episodes, 0.7472 false-warning episodes per hour and zero median lead time. The AI therefore detected more simulated events earlier, but produced more warning episodes per hour and lower warning-episode precision. These results were synthetic-only and did not establish clinical validity.',0),('6.17 Verified AI feature contract',2),('The feature extractor used a causal 120-second history and required at least 12 valid readings per vital, at least 60 seconds of coverage, no timestamp duplicates, no gaps above 15 seconds, valid ranges of 30–42 C, 50–100 percent SpO2 and 40–220 bpm, and an OK-quality terminal reading. The 12 features were the last value, mean, slope per minute and standard deviation for each of temperature, SpO2 and heart rate. Trend flags were raised for temperature slope below -0.08 C/minute or SpO2 slope below -1 percentage point/minute.',0),('6.18 AI limitations and interpretation',2),('The model was a synthetic-only prototype. The train and test sets shared the same synthetic generator, labels were threshold-derived simulated future events, no clinical probability calibration was performed, daily archive data was excluded from time-series training, and false-alarm and lead-time results described the simulated scenarios only. The AI remained independent of the ESP32 local LED, buzzer and display alert path.',0)]
for text,level in items:
    new=OxmlElement('w:p'); target._p.addnext(new); p=Paragraph(new,target._parent); p.style=doc.styles['Heading '+str(level)] if level else doc.styles['Normal']; p.add_run(text); target=p
doc.save(path); print(path)
