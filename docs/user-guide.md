# User guide

1. Open the application and choose **Create an account**. Enter your name, organization, email and a password of at least 12 characters. Keep this password: account recovery is not yet available.
2. Your first workspace is created automatically. Create more from **Workspaces**. All members of an organization share its workspaces in this release; registration currently creates a new organization rather than joining another.
3. Select **Upload Data**. Choose a UTF-8 CSV or XLSX (10 MB, 100,000 rows, 100 columns maximum). For Excel, enter a worksheet name or leave blank for the first sheet. The imported sheet and available sheet names appear in the profile. To analyze another sheet, upload the workbook again with that sheet name.
4. Inspect missing cells, duplicate rows and numeric ranges. The application retains original rows. It does not infer clinical meaning, fix inconsistent units or impute values.
5. Review the semantic role for each column: dimension, date, measure or ignore. Confirm grouping columns as dimension/date and numeric columns as measure. Generate chart saves the current mappings before calculation. If a measure contains non-numeric text, clean the source file and upload it again.
6. Choose a grouping column, calculation and measure. **Count** counts rows in each group and does not use a measure. Sum/mean/min/max use numeric measures and skip missing numeric values. A group with entirely missing measures is shown as — rather than zero. At most 500 groups are allowed; select a lower-cardinality dimension if needed.
7. Select a bar or line chart. Groups sort by label; ISO dates (`YYYY-MM-DD`) sort chronologically. For other date formats, standardize the source before interpreting a line as a time series. The expandable chart data table exposes the same values accessibly.
8. Name and save the analysis. Open **Saved Reports** and download CSV, XLSX or PDF. Excel/PDF include source context and limitations; CSV contains only the exact aggregate table. Exports escape spreadsheet-formula prefixes. The charts themselves are not embedded in PDF exports in this release.
9. In **Marketing Intelligence**, connect Google sources if the administrator configured OAuth. Choose a permitted property, set dates and synchronize. Use **Load metrics** to retrieve previously synchronized data. Freshness is the last successful API sync, not proof that Google has finalized every selected day.
10. Check **Data Pipelines** and click Refresh status for sync history. Missing days are not zero. GSC average position is impression-weighted across imported days and is not live rank. GA4 sessions/event counts are additive; no verified lead or revenue attribution is implemented.

**Try a synthetic example:** manually upload `examples/public_health_demo.csv`, group by district, sum visits. Agona East should show 201 and Winneba 167. These are invented demonstration values.

Use the theme control for light or dark appearance. Sign out using the icon next to your name. Sessions expire after 24 hours. No organization's data should be visible to another organization's user.
