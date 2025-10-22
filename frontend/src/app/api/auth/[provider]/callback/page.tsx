'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { console } from 'inspector'

export default function OAuthCallbackPage({ params }: { params: { provider: string } }) {
  const [isProcessing, setIsProcessing] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const searchParams = useSearchParams()
  const router = useRouter()
  const provider = params.provider

  useEffect(() => {
    const handleOAuthCallback = async () => {
      try {
        const code = searchParams.get('code')
        if (!code) {
          throw new Error('未找到授权码')
        }

        setIsProcessing(true)
        
        // 调用后端API处理回调
        const response = await fetch(`/api/v1/auth/${provider}/callback?code=${code}`)
        
        if (!response.ok) {
          throw new Error('认证失败')
        }
        
        const data = await response.json()
        console.log('API response data:', data)
          
          console.log('原始API数据结构:', JSON.stringify(data, null, 2))
          
          // 保存token
          const token = data.access_token
          if (!token) {
            console.error('没有找到access_token')
            throw new Error('未返回访问令牌')
          }
          
          // 保存token到localStorage
          localStorage.setItem('access_token', token)
          console.log('Token已保存:', token)
          
          // 强制保存用户数据
          try {
            // 优先使用user对象
            const userData = data.user || data
            console.log('准备保存的用户数据:', userData)
            localStorage.setItem('user', JSON.stringify(userData))
            console.log('用户数据已保存到localStorage的user键')
            
            // 同时保存到旧的键名，确保兼容性
            localStorage.setItem('github_user_data', JSON.stringify(userData))
            console.log('用户数据也已保存到github_user_data键')
          } catch (err) {
            console.error('保存用户数据失败:', err)
          }
          
          // 显示成功提示
          toast.success(`${provider === 'dingtalk' ? '钉钉' : 'GitHub'}登录成功！`)
          
          // 延迟跳转，让用户看到成功提示
          setTimeout(() => {
            router.push('/dashboard')
          }, 1000)
      } catch (err: any) {
        console.error('OAuth回调处理错误:', err)
        setError(err.message || '认证过程中出现错误')
        toast.error(`登录失败: ${err.message || '未知错误'}`)
        
        // 5秒后返回登录页面
        setTimeout(() => {
          router.push('/login')
        }, 5000)
      } finally {
        setIsProcessing(false)
      }
    }

    handleOAuthCallback()
  }, [provider, searchParams, router])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center"
        >
          <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
            {provider === 'dingtalk' ? '钉钉' : 'GitHub'} 登录
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            正在处理认证请求，请稍候...
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.5 }}
          className="bg-white p-8 rounded-lg shadow"
        >
          {isProcessing ? (
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mb-4"></div>
              <p className="text-gray-700">正在验证您的身份...</p>
            </div>
          ) : error ? (
            <div className="text-center text-red-600">
              <p className="mb-4">{error}</p>
              <p className="text-sm text-gray-500">将在5秒后返回登录页面...</p>
            </div>
          ) : (
            <div className="text-center text-green-600">
              <p className="mb-4">登录成功！</p>
              <p className="text-sm text-gray-500">正在跳转到仪表板...</p>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}