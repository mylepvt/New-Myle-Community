import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { PlayCircle, CheckCircle, Lock, Award, Download } from 'lucide-react'
import { useTrainingQuery, useMarkTrainingDayMutation, useCertificateStatusQuery, useDownloadCertificateMutation } from '@/hooks/use-training-query'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'

export default function TrainingPage() {
  const { data: trainingData, isLoading, error } = useTrainingQuery()
  const { data: authData } = useAuthMeQuery()
  const markDayMutation = useMarkTrainingDayMutation()
  const { data: certificateStatus } = useCertificateStatusQuery()
  const downloadCertificateMutation = useDownloadCertificateMutation()

  const isTrainingRequired = authData?.training_required

  const handleDownloadCertificate = async () => {
    try {
      await downloadCertificateMutation.mutateAsync()
    } catch (error) {
      console.error('Failed to download certificate:', error)
    }
  }

  const handleMarkDayComplete = async (dayNumber: number) => {
    try {
      await markDayMutation.mutateAsync(dayNumber)
    } catch (error) {
      console.error('Failed to mark day complete:', error)
    }
  }

  const getDayStatus = (dayNumber: number) => {
    const progress = trainingData?.progress.find(p => p.day_number === dayNumber)
    return progress?.completed || false
  }

  const canAccessDay = (dayNumber: number) => {
    if (!isTrainingRequired) return true
    if (dayNumber === 1) return true
    // Check if previous day is completed
    return getDayStatus(dayNumber - 1)
  }

  const getCompletedDays = () => {
    return trainingData?.progress.filter(p => p.completed).length || 0
  }

  if (isLoading) {
    return <div className="flex justify-center p-8">Loading training data...</div>
  }

  if (error) {
    return <div className="flex justify-center p-8 text-red-600">Error loading training data</div>
  }

  if (!isTrainingRequired) {
    return (
      <div className="container mx-auto p-6">
        <Card className="max-w-2xl mx-auto">
          <CardHeader className="text-center">
            <Award className="w-16 h-16 mx-auto text-green-600 mb-4" />
            <CardTitle className="text-2xl text-green-600">Training Completed!</CardTitle>
            <CardDescription>
              You have successfully completed the training program.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <p className="text-gray-600">
              You can access all training materials and resources below.
            </p>
            {certificateStatus?.eligible && (
              <Button onClick={handleDownloadCertificate} disabled={downloadCertificateMutation.isPending}>
                <Download className="w-4 h-4 mr-2" />
                {downloadCertificateMutation.isPending ? 'Downloading...' : 'Download Certificate'}
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  const completedDays = getCompletedDays()
  const totalDays = trainingData?.videos.length || 7

  return (
    <div className="container mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Training Program</h1>
        <p className="text-gray-600">
          Complete the 7-day training program to unlock full access to the platform.
        </p>
        
        <div className="mt-4 p-4 bg-blue-50 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-blue-800 font-medium">Progress</span>
            <span className="text-blue-600">
              {completedDays} / {totalDays} days completed
            </span>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-2 mt-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(completedDays / totalDays) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {trainingData?.note && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-yellow-800">{trainingData.note}</p>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {trainingData?.videos.map((video) => {
          const isCompleted = getDayStatus(video.day_number)
          const canAccess = canAccessDay(video.day_number)
          const isLocked = !canAccess

          return (
            <Card 
              key={video.day_number}
              className={`relative transition-all duration-200 ${
                isCompleted ? 'bg-green-50 border-green-200' : 
                isLocked ? 'bg-gray-50 border-gray-200' : 
                'bg-white border-blue-200 hover:shadow-md'
              }`}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-lg font-semibold">Day {video.day_number}</span>
                    {isCompleted && (
                      <Badge variant="default" className="bg-green-600">
                        <CheckCircle className="w-3 h-3 mr-1" />
                        Completed
                      </Badge>
                    )}
                    {isLocked && (
                      <Badge variant="outline">
                        <Lock className="w-3 h-3 mr-1" />
                        Locked
                      </Badge>
                    )}
                  </div>
                </div>
                <CardTitle className="text-lg">{video.title}</CardTitle>
              </CardHeader>
              
              <CardContent>
                <div className="space-y-4">
                  {video.youtube_url && (
                    <div className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center">
                      <a 
                        href={video.youtube_url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="flex items-center space-x-2 text-blue-600 hover:text-blue-800"
                      >
                        <PlayCircle className="w-8 h-8" />
                        <span>Watch Video</span>
                      </a>
                    </div>
                  )}

                  {!isCompleted && canAccess && (
                    <Button 
                      onClick={() => handleMarkDayComplete(video.day_number)}
                      disabled={markDayMutation.isPending}
                      className="w-full"
                    >
                      {markDayMutation.isPending ? 'Marking...' : 'Mark as Complete'}
                    </Button>
                  )}

                  {isCompleted && (
                    <div className="text-sm text-green-600 text-center">
                      Completed on {new Date(
                        trainingData.progress.find(p => p.day_number === video.day_number)?.completed_at || ''
                      ).toLocaleDateString()}
                    </div>
                  )}

                  {isLocked && (
                    <div className="text-sm text-gray-500 text-center">
                      Complete Day {video.day_number - 1} to unlock
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {completedDays === totalDays && (
        <div className="mt-8 text-center">
          <Card className="max-w-2xl mx-auto">
            <CardHeader>
              <CardTitle className="text-2xl text-green-600">Training Complete!</CardTitle>
              <CardDescription>
                You've completed all training days. Take the certification test to get your certificate.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button size="lg" className="bg-green-600 hover:bg-green-700">
                <Award className="w-4 h-4 mr-2" />
                Take Certification Test
              </Button>
              {certificateStatus?.eligible && (
                <Button onClick={handleDownloadCertificate} disabled={downloadCertificateMutation.isPending} variant="outline">
                  <Download className="w-4 h-4 mr-2" />
                  {downloadCertificateMutation.isPending ? 'Downloading...' : 'Download Certificate'}
                </Button>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
