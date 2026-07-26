(function () {
  var openButton = document.getElementById('open-testcase-import-button');
  var uploadModal = document.getElementById('testcase-import-modal');
  var previewModal = document.getElementById('testcase-import-preview-modal');
  if (!openButton || !uploadModal || !previewModal) {
    return;
  }

  var form = document.getElementById('testcase-import-form');
  var fileInput = document.getElementById('testcase-import-file');
  var errorList = document.getElementById('testcase-import-errors');
  var previewBody = document.getElementById('testcase-import-preview-body');
  var previewCount = document.getElementById('testcase-import-preview-count');
  var confirmButton = document.getElementById('confirm-testcase-import-button');
  var uploadButton = document.getElementById('preview-testcase-import-button');
  var selectedFile = null;
  var needsNewConfirmation = false;

  function setModalOpen(modal, open) {
    modal.classList.toggle('active', open);
    modal.setAttribute('aria-hidden', open ? 'false' : 'true');
  }

  function resetPreview() {
    errorList.innerHTML = '';
    previewBody.innerHTML = '';
    previewCount.textContent = '';
    needsNewConfirmation = false;
    confirmButton.disabled = true;
  }

  function showFileRequiredError() {
    fileInput.classList.remove('is-invalid');
    void fileInput.offsetWidth;
    fileInput.classList.add('is-invalid');
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>'"]/g, function (char) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[char];
    });
  }

  function multiline(value) {
    return escapeHtml(value).replace(/\r?\n/g, '<br>');
  }

  async function upload(url, confirmNew) {
    var data = new FormData();
    data.append('file', selectedFile);
    if (confirmNew) {
      data.append('confirm_new', 'true');
    }
    var response = await fetch(url, { method: 'POST', body: data });
    var payload = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      var error = new Error(payload.error || '上傳失敗');
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function showPreview(data) {
    resetPreview();
    (data.rows || []).forEach(function (row) {
      previewBody.insertAdjacentHTML('beforeend', '<tr>' +
        '<td>' + row.row + '</td><td>' + escapeHtml(row.product) + '</td><td>' + escapeHtml(row.module) + '</td>' +
        '<td>' + multiline(row.case) + '</td><td>' + multiline(row.preconditions) + '</td>' +
        '<td>' + multiline(row.steps) + '</td><td>' + multiline(row.expected_result) + '</td>' +
        '<td>' + escapeHtml(row.priority) + '</td><td>' + multiline(row.remark) + '</td></tr>');
    });
    var pending = [];
    (data.new_products || []).forEach(function (name) { pending.push('新增 Product：' + escapeHtml(name)); });
    (data.new_modules || []).forEach(function (item) { pending.push('新增 Module：' + escapeHtml(item.product) + ' / ' + escapeHtml(item.module)); });
    needsNewConfirmation = pending.length > 0;
    confirmButton.disabled = !data.valid;
    confirmButton.textContent = 'Confirm';
    previewCount.textContent = '共 ' + (data.rows || []).length + ' 筆 TestCase，請確認後匯入';
  }

  function closePreviewAndDiscard() {
    setModalOpen(previewModal, false);
    selectedFile = null;
    fileInput.value = '';
    resetPreview();
  }

  function backToUpload() {
    setModalOpen(previewModal, false);
    setModalOpen(uploadModal, true);
    resetPreview();
  }

  openButton.addEventListener('click', function () { setModalOpen(uploadModal, true); });
  uploadModal.querySelectorAll('[data-close-import-modal]').forEach(function (button) {
    button.addEventListener('click', function () {
      setModalOpen(uploadModal, false);
      selectedFile = null;
      fileInput.value = '';
      resetPreview();
    });
  });
  previewModal.querySelectorAll('[data-close-import-preview-modal]').forEach(function (button) {
    button.addEventListener('click', closePreviewAndDiscard);
  });
  previewModal.querySelectorAll('[data-back-to-import-modal]').forEach(function (button) {
    button.addEventListener('click', backToUpload);
  });
  fileInput.addEventListener('change', function () {
    fileInput.classList.remove('is-invalid');
    resetPreview();
  });

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    selectedFile = fileInput.files[0];
    if (!selectedFile) {
      showFileRequiredError();
      return;
    }
    uploadButton.disabled = true;
    try {
      var payload = await upload('/api/testcases/import/preview', false);
      showPreview(payload.data);
      if (payload.data.valid) {
        setModalOpen(uploadModal, false);
        setModalOpen(previewModal, true);
      } else {
        (payload.data.errors || []).forEach(function (item) {
          errorList.insertAdjacentHTML('beforeend', '<li>第 ' + escapeHtml(item.row) + ' 列：' + escapeHtml(item.message) + '</li>');
        });
        window.showToast('請先修正 Excel 資料錯誤', 'error', 'top-center');
      }
    } catch (error) {
      resetPreview();
      window.showToast('預覽失敗：' + error.message, 'error', 'top-center');
      console.error('[TestCase Import] Preview failed', error);
    } finally {
      uploadButton.disabled = false;
    }
  });

  confirmButton.addEventListener('click', async function () {
    if (!selectedFile) { return; }
    if (needsNewConfirmation && !window.confirm('此操作會建立預覽列出的 Product 與 Module。確定要繼續嗎？')) {
      window.showToast('已取消整批匯入，未建立任何資料。', 'info', 'top-center');
      return;
    }
    confirmButton.disabled = true;
    try {
      var payload = await upload('/api/testcases/import', needsNewConfirmation);
      var result = payload.data;
      setModalOpen(previewModal, false);
      window.showToastAfterReload('匯入成功：' + result.created_testcases + ' 筆 TestCase', 'success', 'top-center');
    } catch (error) {
      window.showToast('匯入失敗：' + error.message, 'error', 'top-center');
      console.error('[TestCase Import] Import failed', error);
      confirmButton.disabled = false;
    }
  });
})();
