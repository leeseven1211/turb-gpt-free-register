// ---------- 概览 ----------
async function loadSummary() {
  if (summaryLoading) return;
  summaryLoading = true;
  try {
    const s = await api('/api/summary');
    $('#statAccounts').textContent = s.accounts;
    $('#statOutlook').textContent = s.outlook_total;
    $('#statAvailable').textContent = s.outlook_available;
    $('#statUsed').textContent = s.outlook_used;
    $('#statFailed').textContent = s.outlook_failed;
    $('#updatedAt').textContent = new Date().toLocaleTimeString();
  } catch(e) {}
  finally { summaryLoading = false; }
}
