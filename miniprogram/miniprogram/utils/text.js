function isQuestionGarble(value) {
  const text = String(value || '').trim()
  if (!text) return false
  const compact = text.replace(/\s/g, '')
  const questionMarks = (compact.match(/\?/g) || []).length
  return questionMarks >= 4 && questionMarks / compact.length >= 0.35
}

function isCorruptedMessage(message) {
  if (!message) return false
  return isQuestionGarble(message.title) || isQuestionGarble(message.content)
}

function filterCorruptedMessages(messages) {
  return (messages || []).filter((message) => !isCorruptedMessage(message))
}

module.exports = {
  filterCorruptedMessages,
  isCorruptedMessage
}
