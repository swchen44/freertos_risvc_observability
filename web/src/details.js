export function showDetails(element, value, title = "事件詳細資料") {
  element.replaceChildren();
  const h = document.createElement("h3");
  h.textContent = title;
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(value, null, 2);
  element.append(h, pre);
}
