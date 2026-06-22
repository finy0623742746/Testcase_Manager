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

async function ensureProduct(productName) {
  return requestJson('/api/products', {
    method: 'POST',
    body: JSON.stringify({ name: productName }),
  });
}

async function ensureModule(productId, moduleName) {
  return requestJson(`/api/products/${productId}/modules`, {
    method: 'POST',
    body: JSON.stringify({ name: moduleName }),
  });
}

async function resolveModuleId(productName, moduleName) {
  const product = await ensureProduct(productName);
  const moduleItem = await ensureModule(product.id, moduleName);
  return moduleItem.id;
}

window.testcaseApi = {
  requestJson,
  resolveModuleId,
};
