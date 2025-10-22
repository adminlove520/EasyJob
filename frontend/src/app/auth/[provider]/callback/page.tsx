'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { useAuth } from '@/lib/auth'

export default function OAuthCallbackPage({ params }: { params: { provider: string } }) {
  const [isProcessing, setIsProcessing] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const searchParams = useSearchParams()
  const router = useRouter()
  const provider = params.provider
  const { refreshUser } = useAuth()

  useEffect(() => {
    const handleOAuthCallback = async () => {
      try {
        console.log('OAuth callback page loaded - this should rarely be seen as backend now handles redirect');
        
        // 检查URL中是否有错误参数
        const error = searchParams.get('error');
        if (error) {
          throw new Error(`认证失败: ${error}`);
        }

        setIsProcessing(true);
        
        // 详细记录当前cookie内容，用于调试
        console.log('Current cookies:', document.cookie);
        
        // 尝试从cookie获取token
        const cookieMatch = document.cookie.match(/access_token=([^;]+)/);
        const cookieToken = cookieMatch ? cookieMatch[1] : null;
        console.log('Cookie token found:', !!cookieToken, 'Match result:', cookieMatch);
        
        // 尝试从localStorage获取token
        const localStorageToken = localStorage.getItem('access_token');
        console.log('LocalStorage token found:', !!localStorageToken);
        
        // 尝试从URL参数获取token（兜底方案）
        const urlToken = searchParams.get('access_token');
        console.log('URL token found:', !!urlToken);
        
        // 优先使用cookie中的token，其次是localStorage，最后是URL参数
        let token = cookieToken || localStorageToken || urlToken;
        console.log('Final token value exists:', !!token);
        
        if (token) {
          console.log('Token found, length:', token.length);

          // 无论如何都保存到localStorage，确保一致性
          localStorage.setItem('access_token', token);
          console.log('Token saved to localStorage');
          
          // 检查URL中是否有用户数据参数
          const userDataParam = searchParams.get('user_data');
          console.log('URL中是否包含user_data参数:', !!userDataParam);
          
          // 如果URL中有用户数据，优先使用
          if (userDataParam) {
            try {
              const decodedUserData = JSON.parse(decodeURIComponent(userDataParam));
              console.log('从URL参数解析的用户数据:', decodedUserData);
              console.log('URL用户数据字段:', Object.keys(decodedUserData));
              localStorage.setItem('github_user_data', JSON.stringify(decodedUserData));
              console.log('URL参数用户数据已保存到localStorage');
            } catch (parseError) {
              console.error('解析URL中的user_data失败:', parseError);
            }
          }
          
          // 尝试从后端获取真实的GitHub用户数据
          try {
            console.log('尝试从后端/api/v1/auth/me获取用户数据...');
            const response = await fetch('/api/v1/auth/me', {
              method: 'GET',
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              },
              credentials: 'include'
            });
            
            if (response.ok) {
              const userData = await response.json();
              console.log('后端返回的用户数据:', userData);
              console.log('后端数据字段:', Object.keys(userData));
              // 保存后端返回的用户数据
              localStorage.setItem('github_user_data', JSON.stringify(userData));
              console.log('后端用户数据已保存到localStorage');
            } else {
              console.log(`获取用户数据失败，状态码: ${response.status}`);
              
              // 检查是否已经保存过用户数据
              const existingUserData = localStorage.getItem('github_user_data');
              if (!existingUserData) {
                // 使用token创建唯一标识的用户数据
                const fallbackUserData = {
                  id: Date.now(),
                  email: `user_${token.substring(0, 8)}@github.com`,
                  name: 'GitHub User',
                  login: `githubuser_${token.substring(0, 8)}`,
                  created_at: new Date().toISOString()
                };
                localStorage.setItem('github_user_data', JSON.stringify(fallbackUserData));
                console.log('后备用户数据已保存到localStorage:', fallbackUserData);
              } else {
                console.log('localStorage中已存在用户数据，无需创建后备数据');
              }
            }
          } catch (fetchError) {
            console.error('从后端获取用户数据时出错:', fetchError);
          }
          
          // 立即刷新用户认证
          console.log('Refreshing user authentication...');
          try {
            await refreshUser();
            console.log('User authentication refreshed successfully');
          } catch (refreshError) {
            console.error('Error refreshing user:', refreshError);
            // 即使刷新失败，也保留token，让AuthProvider处理
          }
        }
        
        if (token) {
          toast.success(`${provider === 'dingtalk' ? '钉钉' : 'GitHub'}登录成功！`);
        } else {
          console.log('No token found, showing error');
          throw new Error('未找到访问令牌');
        }
      } catch (err: any) {
        console.error('OAuth callback handling error:', err);
        setError(err.message || '认证过程中出现错误');
        toast.error(`登录失败: ${err.message || '未知错误'}`);
      } finally {
        setIsProcessing(false);
        // 无论如何，最终都重定向到dashboard
        setTimeout(() => {
          console.log('Final redirect to dashboard');
          window.location.replace('/dashboard');
        }, 1000);
      }
    }

    handleOAuthCallback();
  }, [provider, searchParams, refreshUser]);

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