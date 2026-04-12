import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  User, 
  Bell, 
  Shield, 
  Settings as SettingsIcon,
  Globe,
  Lock,
  Smartphone,
  Mail,
  Phone,
  Calendar,
  Users,
  Database,
  AlertTriangle
} from 'lucide-react'
import { 
  useUserProfileQuery,
  useUserPreferencesQuery,
  useSystemConfigurationQuery,
  useSystemUsersSummaryQuery,
  useUserProfileUpdateMutation,
  useUserPreferencesUpdateMutation,
  useSystemConfigurationUpdateMutation,
  useAppSettingsQuery,
  useAppSettingUpdateMutation,
  useAppSettingDeleteMutation,
  usePasswordChangeMutation,
  useEmailChangeMutation
} from '@/hooks/use-settings-query'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile')
  const { data: authData } = useAuthMeQuery()
  
  // Queries
  const userProfile = useUserProfileQuery()
  const userPreferences = useUserPreferencesQuery()
  const systemConfig = useSystemConfigurationQuery()
  const usersSummary = useSystemUsersSummaryQuery()
  const appSettings = useAppSettingsQuery()
  
  // Mutations
  const updateProfile = useUserProfileUpdateMutation()
  const updatePreferences = useUserPreferencesUpdateMutation()
  const updateSystemConfig = useSystemConfigurationUpdateMutation()
  const updateAppSetting = useAppSettingUpdateMutation()
  const deleteAppSetting = useAppSettingDeleteMutation()
  const changePassword = usePasswordChangeMutation()
  const changeEmail = useEmailChangeMutation()
  
  // Form states
  const [profileForm, setProfileForm] = useState({
    username: '',
    phone: '',
    name: '',
  })
  
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  
  const [emailForm, setEmailForm] = useState({
    new_email: '',
    current_password: '',
  })
  
  const [newSetting, setNewSetting] = useState({
    key: '',
    value: '',
  })

  const isAdmin = authData?.role === 'admin'
  const isLeader = authData?.role === 'leader'

  // Initialize form when profile data loads
  if (userProfile.data && !profileForm.username) {
    setProfileForm({
      username: userProfile.data.username || '',
      phone: userProfile.data.phone || '',
      name: userProfile.data.name || '',
    })
  }

  const handleProfileUpdate = () => {
    updateProfile.mutate(profileForm)
  }

  const handlePasswordChange = () => {
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      alert('Passwords do not match')
      return
    }
    changePassword.mutate(passwordForm)
  }

  const handleEmailChange = () => {
    changeEmail.mutate(emailForm)
  }

  const handlePreferencesUpdate = (key: string, value: boolean) => {
    updatePreferences.mutate({ [key]: value })
  }

  const handleAppSettingUpdate = () => {
    if (!newSetting.key || !newSetting.value) {
      alert('Key and value are required')
      return
    }
    updateAppSetting.mutate(newSetting, {
      onSuccess: () => {
        setNewSetting({ key: '', value: '' })
      }
    })
  }

  const handleAppSettingDelete = (key: string) => {
    if (confirm(`Delete setting "${key}"?`)) {
      deleteAppSetting.mutate(key)
    }
  }

  return (
    <div className="container mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">Settings</h1>
            <p className="text-gray-600">
              Manage your profile, preferences, and system configuration
            </p>
          </div>
          <Badge variant="outline" className="text-sm">
            {authData?.role?.toUpperCase()}
          </Badge>
        </div>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          {isAdmin && <TabsTrigger value="system">System</TabsTrigger>}
          {isAdmin && <TabsTrigger value="advanced">Advanced</TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Basic Information */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center">
                  <User className="w-5 h-5 mr-2" />
                  Basic Information
                </CardTitle>
                <CardDescription>
                  Update your personal information
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="fbo_id">FBO ID</Label>
                  <Input
                    id="fbo_id"
                    value={userProfile.data?.fbo_id || ''}
                    disabled
                    className="bg-gray-50"
                  />
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    value={userProfile.data?.email || ''}
                    disabled
                    className="bg-gray-50"
                  />
                </div>
                <div>
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={profileForm.username}
                    onChange={(e) => setProfileForm(prev => ({ ...prev, username: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="name">Full Name</Label>
                  <Input
                    id="name"
                    value={profileForm.name}
                    onChange={(e) => setProfileForm(prev => ({ ...prev, name: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="phone">Phone</Label>
                  <Input
                    id="phone"
                    value={profileForm.phone}
                    onChange={(e) => setProfileForm(prev => ({ ...prev, phone: e.target.value }))}
                  />
                </div>
                <Button onClick={handleProfileUpdate} disabled={updateProfile.isPending}>
                  {updateProfile.isPending ? 'Updating...' : 'Update Profile'}
                </Button>
              </CardContent>
            </Card>

            {/* Account Status */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center">
                  <Shield className="w-5 h-5 mr-2" />
                  Account Status
                </CardTitle>
                <CardDescription>
                  Your current account status and permissions
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Role</span>
                  <Badge variant={userProfile.data?.role === 'admin' ? 'default' : 'outline'}>
                    {userProfile.data?.role}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Registration Status</span>
                  <Badge variant={userProfile.data?.registration_status === 'approved' ? 'default' : 'secondary'}>
                    {userProfile.data?.registration_status}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Training Status</span>
                  <Badge variant={userProfile.data?.training_status === 'completed' ? 'default' : 'outline'}>
                    {userProfile.data?.training_status}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Access Status</span>
                  <Badge variant={userProfile.data?.access_blocked ? 'destructive' : 'default'}>
                    {userProfile.data?.access_blocked ? 'Blocked' : 'Active'}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Member Since</span>
                  <span className="text-sm text-gray-600">
                    {new Date(userProfile.data?.created_at || '').toLocaleDateString()}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Preferences Tab */}
        <TabsContent value="preferences" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center">
                <Bell className="w-5 h-5 mr-2" />
                Notification Preferences
              </CardTitle>
              <CardDescription>
                Choose how you want to receive notifications
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {userPreferences.data && (
                <>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label htmlFor="email_notifications">Email Notifications</Label>
                      <p className="text-sm text-gray-600">Receive notifications via email</p>
                    </div>
                    <Switch
                      id="email_notifications"
                      checked={userPreferences.data.email_notifications}
                      onCheckedChange={(checked) => handlePreferencesUpdate('email_notifications', checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label htmlFor="push_notifications">Push Notifications</Label>
                      <p className="text-sm text-gray-600">Receive browser push notifications</p>
                    </div>
                    <Switch
                      id="push_notifications"
                      checked={userPreferences.data.push_notifications}
                      onCheckedChange={(checked) => handlePreferencesUpdate('push_notifications', checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label htmlFor="daily_report_reminders">Daily Report Reminders</Label>
                      <p className="text-sm text-gray-600">Get reminded to submit daily reports</p>
                    </div>
                    <Switch
                      id="daily_report_reminders"
                      checked={userPreferences.data.daily_report_reminders}
                      onCheckedChange={(checked) => handlePreferencesUpdate('daily_report_reminders', checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label htmlFor="lead_assignment_alerts">Lead Assignment Alerts</Label>
                      <p className="text-sm text-gray-600">Notify when new leads are assigned</p>
                    </div>
                    <Switch
                      id="lead_assignment_alerts"
                      checked={userPreferences.data.lead_assignment_alerts}
                      onCheckedChange={(checked) => handlePreferencesUpdate('lead_assignment_alerts', checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label htmlFor="payment_notifications">Payment Notifications</Label>
                      <p className="text-sm text-gray-600">Get notified about payment updates</p>
                    </div>
                    <Switch
                      id="payment_notifications"
                      checked={userPreferences.data.payment_notifications}
                      onCheckedChange={(checked) => handlePreferencesUpdate('payment_notifications', checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label htmlFor="weekly_summary">Weekly Summary</Label>
                      <p className="text-sm text-gray-600">Receive weekly performance summary</p>
                    </div>
                    <Switch
                      id="weekly_summary"
                      checked={userPreferences.data.weekly_summary}
                      onCheckedChange={(checked) => handlePreferencesUpdate('weekly_summary', checked)}
                    />
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Change Password */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center">
                  <Lock className="w-5 h-5 mr-2" />
                  Change Password
                </CardTitle>
                <CardDescription>
                  Update your account password
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="current_password">Current Password</Label>
                  <Input
                    id="current_password"
                    type="password"
                    value={passwordForm.current_password}
                    onChange={(e) => setPasswordForm(prev => ({ ...prev, current_password: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="new_password">New Password</Label>
                  <Input
                    id="new_password"
                    type="password"
                    value={passwordForm.new_password}
                    onChange={(e) => setPasswordForm(prev => ({ ...prev, new_password: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="confirm_password">Confirm New Password</Label>
                  <Input
                    id="confirm_password"
                    type="password"
                    value={passwordForm.confirm_password}
                    onChange={(e) => setPasswordForm(prev => ({ ...prev, confirm_password: e.target.value }))}
                  />
                </div>
                <Button onClick={handlePasswordChange} disabled={changePassword.isPending}>
                  {changePassword.isPending ? 'Changing...' : 'Change Password'}
                </Button>
              </CardContent>
            </Card>

            {/* Change Email */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center">
                  <Mail className="w-5 h-5 mr-2" />
                  Change Email
                </CardTitle>
                <CardDescription>
                  Update your email address
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="new_email">New Email</Label>
                  <Input
                    id="new_email"
                    type="email"
                    value={emailForm.new_email}
                    onChange={(e) => setEmailForm(prev => ({ ...prev, new_email: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="email_password">Current Password</Label>
                  <Input
                    id="email_password"
                    type="password"
                    value={emailForm.current_password}
                    onChange={(e) => setEmailForm(prev => ({ ...prev, current_password: e.target.value }))}
                  />
                </div>
                <Button onClick={handleEmailChange} disabled={changeEmail.isPending}>
                  {changeEmail.isPending ? 'Changing...' : 'Change Email'}
                </Button>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* System Tab (Admin Only) */}
        {isAdmin && (
          <TabsContent value="system" className="space-y-6">
            {/* Users Summary */}
            {usersSummary.data && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg flex items-center">
                    <Users className="w-5 h-5 mr-2" />
                    Users Summary
                  </CardTitle>
                  <CardDescription>
                    Overview of all users in the system
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold">{usersSummary.data.total_users}</div>
                      <div className="text-sm text-gray-600">Total Users</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-red-600">{usersSummary.data.blocked_users}</div>
                      <div className="text-sm text-gray-600">Blocked Users</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">{usersSummary.data.by_role.admin || 0}</div>
                      <div className="text-sm text-gray-600">Admins</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">{usersSummary.data.by_role.leader || 0}</div>
                      <div className="text-sm text-gray-600">Leaders</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Feature Flags */}
            {systemConfig.data && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg flex items-center">
                    <SettingsIcon className="w-5 h-5 mr-2" />
                    Feature Flags
                  </CardTitle>
                  <CardDescription>
                    Enable or disable system features
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {Object.entries(systemConfig.data.feature_flags).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <div>
                        <Label htmlFor={key}>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</Label>
                        <p className="text-sm text-gray-600">Toggle {key} feature</p>
                      </div>
                      <Switch
                        id={key}
                        checked={value}
                        onCheckedChange={(checked) => updateSystemConfig.mutate({ [key]: checked })}
                      />
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </TabsContent>
        )}

        {/* Advanced Tab (Admin Only) */}
        {isAdmin && (
          <TabsContent value="advanced" className="space-y-6">
            {/* App Settings */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center">
                  <Database className="w-5 h-5 mr-2" />
                  Application Settings
                </CardTitle>
                <CardDescription>
                  Manage application configuration
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Add New Setting */}
                <div className="space-y-4">
                  <h4 className="font-medium">Add New Setting</h4>
                  <div className="flex gap-2">
                    <Input
                      placeholder="Key"
                      value={newSetting.key}
                      onChange={(e) => setNewSetting(prev => ({ ...prev, key: e.target.value }))}
                    />
                    <Input
                      placeholder="Value"
                      value={newSetting.value}
                      onChange={(e) => setNewSetting(prev => ({ ...prev, value: e.target.value }))}
                    />
                    <Button onClick={handleAppSettingUpdate} disabled={updateAppSetting.isPending}>
                      Add
                    </Button>
                  </div>
                </div>

                {/* Existing Settings */}
                {appSettings.data && (
                  <div className="space-y-4">
                    <h4 className="font-medium">Current Settings</h4>
                    <div className="space-y-2">
                      {Object.entries(appSettings.data.settings).map(([key, value]) => (
                        <div key={key} className="flex items-center justify-between p-2 border rounded">
                          <div>
                            <div className="font-medium">{key}</div>
                            <div className="text-sm text-gray-600">{value}</div>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleAppSettingDelete(key)}
                            disabled={deleteAppSetting.isPending}
                          >
                            Delete
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
