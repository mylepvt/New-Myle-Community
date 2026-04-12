import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
  Phone, 
  Mail, 
  MapPin, 
  Clock, 
  DollarSign,
  ChevronDown,
  User
} from 'lucide-react'
import { useAvailableTransitionsQuery } from '@/hooks/use-pipeline-query'
import type { PipelineLead } from '@/hooks/use-pipeline-query'

interface PipelineColumnProps {
  status: string
  statusLabel: string
  leads: PipelineLead[]
  onStatusTransition: (leadId: number, newStatus: string) => void
  selectedLead: number | null
  onSelectLead: (leadId: number | null) => void
  userRole: string
}

const STATUS_COLORS = {
  new_lead: 'bg-blue-100 border-blue-200',
  contacted: 'bg-yellow-100 border-yellow-200',
  invited: 'bg-purple-100 border-purple-200',
  video_sent: 'bg-indigo-100 border-indigo-200',
  video_watched: 'bg-pink-100 border-pink-200',
  paid: 'bg-green-100 border-green-200',
  day1: 'bg-orange-100 border-orange-200',
  day2: 'bg-orange-100 border-orange-200',
  interview: 'bg-red-100 border-red-200',
  track_selected: 'bg-teal-100 border-teal-200',
  seat_hold: 'bg-cyan-100 border-cyan-200',
  converted: 'bg-emerald-100 border-emerald-200',
  lost: 'bg-gray-100 border-gray-200',
}

export default function PipelineColumn({
  status,
  statusLabel,
  leads,
  onStatusTransition,
  selectedLead,
  onSelectLead,
  userRole,
}: PipelineColumnProps) {
  const [expandedLead, setExpandedLead] = useState<number | null>(null)
  
  // Get available transitions for expanded lead
  const { data: transitions } = useAvailableTransitionsQuery(
    expandedLead || 0
  )

  const handleLeadClick = (leadId: number) => {
    if (selectedLead === leadId) {
      onSelectLead(null)
      setExpandedLead(null)
    } else {
      onSelectLead(leadId)
      setExpandedLead(leadId)
    }
  }

  const handleTransition = (newStatus: string) => {
    if (expandedLead) {
      onStatusTransition(expandedLead, newStatus)
      setExpandedLead(null)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Column Header */}
      <div className="mb-4">
        <Card className={`${STATUS_COLORS[status as keyof typeof STATUS_COLORS] || 'bg-gray-50 border-gray-200'}`}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">{statusLabel}</CardTitle>
              <Badge variant="outline" className="text-xs">
                {leads.length}
              </Badge>
            </div>
          </CardHeader>
        </Card>
      </div>

      {/* Leads List */}
      <div className="flex-1 space-y-2 overflow-y-auto">
        {leads.map((lead) => (
          <Card
            key={lead.id}
            className={`cursor-pointer transition-all duration-200 ${
              selectedLead === lead.id
                ? 'ring-2 ring-blue-500 shadow-md'
                : 'hover:shadow-md'
            } ${STATUS_COLORS[status as keyof typeof STATUS_COLORS] || 'bg-white'}`}
            onClick={() => handleLeadClick(lead.id)}
          >
            <CardContent className="p-3">
              {/* Lead Header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <User className="w-4 h-4 text-gray-500" />
                  <span className="font-medium text-sm truncate">{lead.name}</span>
                </div>
                {lead.payment_status && (
                  <Badge variant="outline" className="text-xs">
                    <DollarSign className="w-3 h-3 mr-1" />
                    {lead.payment_status}
                  </Badge>
                )}
              </div>

              {/* Contact Info */}
              <div className="space-y-1 text-xs text-gray-600">
                {lead.phone && (
                  <div className="flex items-center space-x-1">
                    <Phone className="w-3 h-3" />
                    <span>{lead.phone}</span>
                  </div>
                )}
                {lead.email && (
                  <div className="flex items-center space-x-1">
                    <Mail className="w-3 h-3" />
                    <span className="truncate">{lead.email}</span>
                  </div>
                )}
                {lead.city && (
                  <div className="flex items-center space-x-1">
                    <MapPin className="w-3 h-3" />
                    <span>{lead.city}</span>
                  </div>
                )}
              </div>

              {/* Created At */}
              <div className="flex items-center space-x-1 mt-2 text-xs text-gray-500">
                <Clock className="w-3 h-3" />
                <span>{new Date(lead.created_at).toLocaleDateString()}</span>
              </div>

              {/* Expanded View */}
              {expandedLead === lead.id && transitions && (
                <div className="mt-3 pt-3 border-t border-gray-200">
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-gray-700">Move to:</p>
                    <div className="grid grid-cols-1 gap-1">
                      {transitions.map((transition) => (
                        <Button
                          key={transition}
                          size="sm"
                          variant="outline"
                          className="text-xs h-7 justify-start"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleTransition(transition)
                          }}
                        >
                          <ChevronDown className="w-3 h-3 mr-1" />
                          {transition.replace('_', ' ').toUpperCase()}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Empty State */}
      {leads.length === 0 && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-gray-500">
            <User className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-xs">No leads</p>
          </div>
        </div>
      )}
    </div>
  )
}
