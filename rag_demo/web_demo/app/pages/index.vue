<script setup lang="ts">
import type { RagQueryResponse } from '../types/rag'

const question = ref('')
const includeDebug = ref(false)
const loading = ref(false)
const indexing = ref(false)
const uploading = ref(false)
const health = ref<'checking' | 'ok' | 'down'>('checking')
const errorMsg = ref('')
const indexMsg = ref('')
const uploadMsg = ref('')
const result = ref<RagQueryResponse | null>(null)
const selectedFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const { queryRag, buildIndex, checkHealth, uploadFile, ping, clearFiles } = useRagApi()

let pingInterval: ReturnType<typeof setInterval> | null = null

const handleBeforeUnload = () => {
  // Use sendBeacon for more reliable delivery during unload if necessary
  // Or simply fire the standard fetch.
  clearFiles()
}

onMounted(async () => {
  try {
    const res = await checkHealth()
    health.value = res.status === 'ok' ? 'ok' : 'down'
  } catch {
    health.value = 'down'
  }

  // Set up 1-minute heartbeat
  pingInterval = setInterval(() => {
    ping().catch(() => {})
  }, 60000)

  // Set up cleanup on window close or reload
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onUnmounted(() => {
  if (pingInterval) {
    clearInterval(pingInterval)
  }
  window.removeEventListener('beforeunload', handleBeforeUnload)
  clearFiles().catch(() => {})
})

const submitQuery = async () => {
  errorMsg.value = ''
  result.value = null
  if (!question.value.trim()) {
    return
  }

  loading.value = true
  try {
    result.value = await queryRag({ question: question.value, include_debug: includeDebug.value })
  } catch (error: any) {
    errorMsg.value = error?.data?.message || error?.message || '查詢失敗'
  } finally {
    loading.value = false
  }
}

const runIndex = async () => {
  indexMsg.value = ''
  indexing.value = true
  try {
    const res = await buildIndex()
    indexMsg.value = `建索引完成，chunks: ${res.chunks}`
  } catch (error: any) {
    if (error?.data?.code === 'NO_PDF_FOUND') {
      indexMsg.value = '建立索引失敗：目錄下尚未找到任何 PDF 檔案，請先在上方「上傳新文件」區塊上傳您的資料。'
    } else {
      indexMsg.value = error?.data?.message || error?.message || '建索引失敗'
    }
  } finally {
    indexing.value = false
  }
}

const runUpload = async () => {
  if (!selectedFile.value) return
  uploadMsg.value = ''
  uploading.value = true
  try {
    const res = await uploadFile(selectedFile.value)
    uploadMsg.value = `上傳成功: ${res.filename}`
    selectedFile.value = null
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  } catch (error: any) {
    uploadMsg.value = error?.data?.message || error?.message || '上傳失敗'
  } finally {
    uploading.value = false
  }
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0] || null
  } else {
    selectedFile.value = null
  }
}

const healthColor = computed(() => {
  if (health.value === 'ok') return 'success'
  if (health.value === 'down') return 'error'
  return 'neutral'
})
</script>

<template>
  <div class="space-y-8 max-w-4xl mx-auto">
    <!-- Header Area -->
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div>
        <h1 class="text-3xl font-bold tracking-tight">RAG 系統主控台</h1>
        <p class="text-(--ui-text-muted) mt-1">
          管理您的檢索增強生成系統，建立索引並進行即時問答。
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-sm text-(--ui-text-muted)">FastAPI 狀態:</span>
        <UBadge :color="healthColor" variant="subtle" class="capitalize">
          {{ health }}
        </UBadge>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Left Column: Query and Management -->
      <div class="lg:col-span-2 space-y-8">
        <!-- Index Management (Moved here) -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-database" class="w-5 h-5 text-(--ui-primary)" />
              <h2 class="font-semibold">系統設定 (文件管理與索引)</h2>
            </div>
          </template>

          <div class="space-y-6">
            <!-- Upload Section -->
            <div class="space-y-3">
              <h3 class="text-sm font-medium">1. 上傳新文件 (PDF)</h3>
              <p class="text-xs text-(--ui-text-muted)">
                上傳新的年報或說明書至伺服器作為知識庫擴充來源。
              </p>
              <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                <input
                  ref="fileInput"
                  type="file"
                  accept=".pdf"
                  class="block w-full text-sm text-(--ui-text-muted)
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-md file:border-0
                    file:text-sm file:font-semibold
                    file:bg-(--ui-primary)/10 file:text-(--ui-primary)
                    hover:file:bg-(--ui-primary)/20"
                  @change="handleFileSelect"
                />
                <UButton
                  :loading="uploading"
                  :disabled="!selectedFile"
                  icon="i-lucide-upload"
                  color="primary"
                  class="shrink-0"
                  @click="runUpload"
                >
                  上傳檔案
                </UButton>
              </div>
              <UAlert
                v-if="uploadMsg"
                :color="uploadMsg.includes('失敗') ? 'error' : 'success'"
                variant="subtle"
                :title="uploadMsg"
              />
            </div>

            <USeparator />

            <!-- Index Section -->
            <div class="space-y-3">
              <h3 class="text-sm font-medium">2. 建立/更新索引</h3>
              <p class="text-xs text-(--ui-text-muted)">
                如果您已經上傳了新文件，請重新建立索引以確保 AI 能讀取到最新內容。
              </p>
              <UButton
                block
                :loading="indexing"
                icon="i-lucide-refresh-cw"
                color="neutral"
                variant="outline"
                @click="runIndex"
              >
                {{ indexing ? '建索引中...' : '重新建立索引' }}
              </UButton>
              
              <UAlert
                v-if="indexMsg"
                :color="indexMsg.includes('失敗') ? 'error' : 'success'"
                variant="subtle"
                :title="indexMsg"
              />
            </div>
          </div>
        </UCard>

        <!-- Index Creation Reminder -->
        <UAlert
          icon="i-lucide-info"
          color="primary"
          variant="subtle"
          title="使用提示"
          description="在開始提問之前，請確保您已建立索引。如果您的文件有變動，請點擊上方的「重新建立索引」按鈕。"
        />

        <!-- Query Section -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-message-square" class="w-5 h-5 text-(--ui-primary)" />
              <h2 class="font-semibold">AI 問答</h2>
            </div>
          </template>

          <form @submit.prevent="submitQuery" class="space-y-6 flex flex-col items-center">
            <UFormField label="您的問題" help="請輸入您想詢問 RAG 系統的問題" class="w-full ">
              <UTextarea
                v-model="question"
                placeholder="例如：請總結這份產品說明書..."
                :rows="6"
                autoresize
                block
              />
            </UFormField>

            <div class="flex items-center justify-between w-full">
              <UCheckbox v-model="includeDebug" label="包含除錯資訊 (Debug Info)" />
              <UButton
                type="submit"
                :loading="loading"
                icon="i-lucide-send"
                :disabled="!question.trim()"
              >
                {{ loading ? '查詢中...' : '送出問題' }}
              </UButton>
            </div>
          </form>

          <UAlert
            v-if="errorMsg"
            icon="i-lucide-circle-alert"
            color="error"
            variant="subtle"
            :title="errorMsg"
            class="mt-4"
          />
        </UCard>

        <!-- Result Section -->
        <UCard v-if="result" class="ring-2 ring-(--ui-primary)/20">
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-bot" class="w-5 h-5 text-(--ui-primary)" />
              <h2 class="font-semibold">回答結果</h2>
            </div>
          </template>

          <div class="space-y-6">
            <div>
              <h3 class="text-sm font-medium text-(--ui-text-muted) mb-2 uppercase tracking-wider">回答內容</h3>
              <p class="text-lg leading-relaxed">{{ result.answer }}</p>
            </div>

            <div v-if="result.refusal" class="p-4 bg-orange-50 dark:bg-orange-950/20 rounded-lg border border-orange-200 dark:border-orange-800">
              <p class="text-sm font-medium text-orange-800 dark:text-orange-300">拒絕回覆:</p>
              <p class="text-sm mt-1">{{ result.refusal }}</p>
            </div>

            <div v-if="result.sources?.length" class="space-y-2">
              <h3 class="text-sm font-medium text-(--ui-text-muted) uppercase tracking-wider">參考來源</h3>
              <div class="flex flex-wrap gap-2">
                <UBadge v-for="source in result.sources" :key="source" variant="outline" color="neutral">
                  {{ source }}
                </UBadge>
              </div>
            </div>

            <UCollapsible v-if="includeDebug && result.retrieval_debug">
              <UButton variant="ghost" color="neutral" size="sm" icon="i-lucide-code" class="mt-4">
                查看檢索除錯資訊
              </UButton>
              <template #content>
                <div class="mt-2 p-4 bg-slate-900 rounded-lg overflow-x-auto">
                  <pre class="text-xs text-slate-300 font-mono">{{ result.retrieval_debug }}</pre>
                </div>
              </template>
            </UCollapsible>
          </div>
        </UCard>
      </div>

      <!-- Right Column: Sidebar -->
      <div class="space-y-8">
        <!-- Quick Tips -->
        <UCard variant="subtle">
          <h3 class="font-medium text-sm mb-2">使用小撇步</h3>
          <ul class="text-xs space-y-2 text-(--ui-text-muted) list-disc pl-4">
            <li>問題越精確，回答越準確。</li>
            <li>開啟除錯資訊可以幫助了解系統是如何檢索文件的。</li>
            <li>若回答異常，請檢查索引狀態。</li>
          </ul>
        </UCard>
      </div>
    </div>
  </div>
</template>
