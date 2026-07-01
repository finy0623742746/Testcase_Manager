async function requestJson(url, options) {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options && options.headers ? options.headers : {}),
    },
    ...options,
  });

  let payload = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    payload = await response.json();
  } else {
    const text = await response.text();
    payload = text ? { message: text } : null;
  }

  if (!response.ok) {
    const message =
      (payload && (payload.error || payload.message)) ||
      `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

window.testrunApi = {
  requestJson,
  list: () => requestJson('/api/testruns'),
  get: (id) => requestJson(`/api/testruns/${id}`),
  create: (payload) => requestJson('/api/testruns', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  delete: (id) => requestJson(`/api/testruns/${id}`, {
    method: 'DELETE',
  }),
  updateStatus: (testrunId, testCaseId, status) =>
    requestJson(`/api/testruns/${testrunId}/testcases/${testCaseId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status }),
    }),
};
