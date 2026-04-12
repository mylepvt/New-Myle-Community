import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
  Users, 
  TrendingUp, 
  Phone, 
  Video, 
  DollarSign, 
  Calendar,
  Target,
  RefreshCw,
  Settings
} from 'lucide-react'
import { 
  usePipelineViewQuery, 
  usePipelineMetricsQuery,
  useTransitionLeadMutation,
  useAutoExpireMutation,
  usePipelineStatusesQuery
} from '@/hooks/use-pipeline-query'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import PipelineColumn from '@/components/pipeline/PipelineColumn'
import PipelineMetrics from '@/components/pipeline/PipelineMetrics'

export default function PipelinePage() {
  const { data: pipelineData, isLoading, error } = usePipelineViewQuery()
  const { data: metrics } = usePipelineMetricsQuery()
  const { data: authData } = useAuthMeQuery()
  const transitionMutation = useTransitionLeadMutation()
  const autoExpireMutation = useAutoExpireMutation()
  const { data: statuses } = usePipelineStatusesQuery()
  
  const [selectedLead, setSelectedLead] = useState<number | null>(null)

  const handleStatusTransition = async (leadId: number, newStatus: string) => {
    try {
      await transitionMutation.mutateAsync({ leadId, targetStatus: newStatus })
    } catch (error) {
      console.error('Failed to transition lead:', error)
    }
  }

  const handleAutoExpire = async () => {
    try {
      await autoExpireMutation.mutateAsync()
    } catch (error) {
      console.error('Failed to auto-expire leads:', error)
    }
  }

  if (isLoading) {
    return <div className="flex justify-center p-8">Loading pipeline...</div>
  }

  if (error) {
    return <div className="flex justify-center p-8 text-red-600">Error loading pipeline</div>
  }

  if (!pipelineData) {
    return <div className="flex justify-center p-8">No pipeline data available</div>
  }

  const isAdminOrLeader = authData?.role === 'admin' || authData?.role === 'leader'

  return (
    <div className="container mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">Lead Pipeline</h1>
            <p className="text-gray-600">
              Manage leads through the conversion funnel
            </p>
          </div>
          <div className="flex items-center space-x-4">
            {isAdminOrLeader && (
              <Button 
                onClick={handleAutoExpire}
                disabled={autoExpireMutation.isPending}
                variant="outline"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Auto-Expire
              </Button>
            )}
            <Badge variant="outline" className="text-sm">
              {pipelineData.user_role.toUpperCase()}
            </Badge>
          </div>
        </div>
      </div>

      {/* Metrics Overview */}
      {metrics && (
        <div className="mb-8">
          <PipelineMetrics metrics={metrics} />
        </div>
      )}

      {/* Pipeline Columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {pipelineData.columns.map((status) => {
          const leads = pipelineData.leads_by_status[status] || []
          const statusLabel = pipelineData.status_labels[status] || status
          
          return (
            <PipelineColumn
              key={status}
              status={status}
              statusLabel={statusLabel}
              leads={leads}
              onStatusTransition={handleStatusTransition}
              selectedLead={selectedLead}
              onSelectLead={setSelectedLead}
              userRole={pipelineData.user_role}
            />
          )
        })}
      </div>

      {/* Empty State */}
      {pipelineData.total_leads === 0 && (
        <div className="text-center py-12">
          <Users className="w-16 h-16 mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No leads in pipeline</h3>
          <p className="text-gray-600">
            Start adding leads to see them in the pipeline view.
          </p>
        </div>
      )}
    </div>
  )
}
