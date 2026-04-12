import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type TrainingVideo = {
  day_number: number
  title: string
  youtube_url?: string
}

export type TrainingProgress = {
  day_number: number
  completed: boolean
  completed_at?: string
}

export type TrainingSurfaceResponse = {
  videos: TrainingVideo[]
  progress: TrainingProgress[]
  note?: string
}

export type TrainingTestQuestion = {
  id: number
  question: string
  options: {
    a: string
    b: string
    c: string
    d: string
  }
}

export type TrainingTestResult = {
  score: number
  total_questions: number
  percent: number
  passed: boolean
  pass_mark_percent: number
  attempted_at: string
  training_completed: boolean
}

export async function fetchTrainingSurface(): Promise<TrainingSurfaceResponse> {
  const res = await apiFetch('/api/v1/system/training')
  if (!res.ok) {
    throw new Error(`Training surface HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchTrainingTestQuestions(): Promise<TrainingTestQuestion[]> {
  const res = await apiFetch('/api/v1/system/training-test/questions')
  if (!res.ok) {
    throw new Error(`Training test questions HTTP ${res.status}`)
  }
  return res.json()
}

export async function submitTrainingTest(answers: Record<string, string>): Promise<TrainingTestResult> {
  const res = await apiFetch('/api/v1/system/training-test/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  })
  if (!res.ok) {
    throw new Error(`Training test submit HTTP ${res.status}`)
  }
  return res.json()
}

export async function markTrainingDay(dayNumber: number): Promise<TrainingSurfaceResponse> {
  const res = await apiFetch('/api/v1/system/training/mark-day', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ day_number: dayNumber }),
  })
  if (!res.ok) {
    throw new Error(`Mark training day HTTP ${res.status}`)
  }
  return res.json()
}

export function useTrainingQuery() {
  return useQuery({
    queryKey: ['training', 'surface'],
    queryFn: fetchTrainingSurface,
    staleTime: 30_000,
  })
}

export function useTrainingTestQuestionsQuery() {
  return useQuery({
    queryKey: ['training', 'test', 'questions'],
    queryFn: fetchTrainingTestQuestions,
    staleTime: 60_000,
  })
}

export function useMarkTrainingDayMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: markTrainingDay,
    onSuccess: (data) => {
      queryClient.setQueryData(['training', 'surface'], data)
    },
  })
}

export function useSubmitTrainingTestMutation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: submitTrainingTest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training', 'surface'] })
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })
}

export type CertificateStatus = {
  eligible: boolean
  requirements: {
    all_days_completed: boolean
    test_passed: boolean
    training_completed: boolean
  }
  completed_days: number[]
  total_days: number
  latest_test_score?: number
  latest_test_total?: number
  latest_test_passed: boolean
}

export async function fetchCertificateStatus(): Promise<CertificateStatus> {
  const res = await apiFetch('/api/v1/training/certificate/status')
  if (!res.ok) {
    throw new Error(`Certificate status HTTP ${res.status}`)
  }
  return res.json()
}

export async function downloadCertificate(): Promise<Blob> {
  const res = await apiFetch('/api/v1/training/certificate')
  if (!res.ok) {
    throw new Error(`Certificate download HTTP ${res.status}`)
  }
  return res.blob()
}

export function useCertificateStatusQuery() {
  return useQuery({
    queryKey: ['training', 'certificate', 'status'],
    queryFn: fetchCertificateStatus,
    staleTime: 30_000,
  })
}

export function useDownloadCertificateMutation() {
  return useMutation({
    mutationFn: downloadCertificate,
    onSuccess: (blob) => {
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `training_certificate_${new Date().toISOString().split('T')[0]}.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    },
  })
}
