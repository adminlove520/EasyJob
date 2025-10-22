'use client'

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'

// 用户接口定义
interface User {
  id: number
  email: string
  full_name?: string
  is_active: boolean
  created_at: string
}

// 登录响应接口
interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

// 注册请求接口
interface RegisterRequest {
  email: string
  password: string
  full_name: string
}

// 认证上下文接口
interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<boolean>
  register: (email: string, password: string, fullName: string) => Promise<boolean>
  logout: () => void
  updateUser: (userData: Partial<User>) => void
  refreshUser: () => Promise<void>
}

// 创建认证上下文
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// API基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 获取cookie中的token
const getCookieToken = (): string | null => {
  const cookie = document.cookie;
  const cookieMatch = cookie.match(/access_token=([^;]+)/);
  return cookieMatch ? cookieMatch[1] : null;
}

// 获取token（优先从cookie，其次从localStorage）
const getToken = (): string | null => {
  return getCookieToken() || localStorage.getItem('access_token');
}

// 认证相关API调用
class AuthAPI {
  private static getAuthHeaders(): Record<string, string> {
    const token = getToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  static async login(email: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      credentials: 'include', // 允许跨域请求携带凭证
      body: new URLSearchParams({
        username: email,
        password: password,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '登录失败')
    }

    return response.json()
  }

  static async register(data: RegisterRequest): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // 允许跨域请求携带凭证
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '注册失败')
    }

    return response.json()
  }

  static async getCurrentUser(): Promise<User> {
    console.log('===== 获取用户数据开始 =====');
    
    // 检查localStorage中的所有可能的键
    const userDataStr = localStorage.getItem('user');
    const githubUserDataStr = localStorage.getItem('github_user_data');
    const token = localStorage.getItem('access_token');
    
    console.log('localStorage状态:');
    console.log('- access_token存在:', token ? '是' : '否');
    console.log('- user键存在:', userDataStr ? '是' : '否');
    console.log('- github_user_data键存在:', githubUserDataStr ? '是' : '否');
    
    // 创建一个对象来存储所有可能的用户数据来源
    const userDataSources = {
      'user键': userDataStr ? JSON.parse(userDataStr) : null,
      'github_user_data键': githubUserDataStr ? JSON.parse(githubUserDataStr) : null
    };
    
    // 遍历所有数据源，查找包含用户名和邮箱的数据
    for (const [source, data] of Object.entries(userDataSources)) {
      if (data) {
        console.log(`从${source}解析出的数据:`, data);
        
        // 打印原始数据的所有字段，帮助调试
        console.log(`从${source}获取的用户数据包含的字段:`, Object.keys(data));
        
        // 检查是否包含用户名或邮箱信息
        const hasUsername = data.login || data.name || data.full_name || data.user_name;
        const hasEmail = data.email || data.user_email || data.email_address;
        
        console.log(`从${source} - 用户名信息存在:`, hasUsername ? '是' : '否');
        console.log(`从${source} - 邮箱信息存在:`, hasEmail ? '是' : '否');
        
        // 创建用户对象，使用所有可能的字段名
        const user: User = {
          id: data.id || data.user_id || 0,
          email: data.email || data.user_email || data.email_address || '',
          full_name: data.login || data.name || data.full_name || data.user_name || 'Unknown User',
          is_active: true,
          created_at: data.created_at || new Date().toISOString()
        };
        
        console.log(`从${source}返回的用户信息:`, user);
        console.log('===== 获取用户数据结束 =====');
        return user;
      }
    }
    
    // 如果有token但没有用户数据，尝试直接使用token相关信息
    if (token) {
      console.log('只有token但没有用户数据，使用token创建基本用户信息');
      const user: User = {
        id: 0,
        email: '',
        full_name: 'Authenticated User',
        is_active: true,
        created_at: new Date().toISOString()
      };
      console.log('使用token创建的用户信息:', user);
      console.log('===== 获取用户数据结束 =====');
      return user;
    }
    
    console.log('未找到有效的用户数据');
    console.log('===== 获取用户数据结束 =====');
    
    // 默认返回
    return {
      id: 0,
      email: '',
      full_name: 'Unknown User',
      is_active: true,
      created_at: new Date().toISOString()
    };
  }
}

// 认证提供者组件
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const isAuthenticated = !!user

  // 登录函数
  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const response = await AuthAPI.login(email, password)
      
      // 保存token到localStorage
      localStorage.setItem('access_token', response.access_token)
      
      // 设置用户信息
      setUser(response.user)
      
      return true
    } catch (error) {
      console.error('Login error:', error)
      // 抛出错误以便上层处理
      throw error
    }
  }

  // 注册函数
  const register = async (email: string, password: string, fullName: string): Promise<boolean> => {
    try {
      const user = await AuthAPI.register({
        email,
        password,
        full_name: fullName,
      })
      
      // 注册成功后自动登录
      return await login(email, password)
    } catch (error) {
      console.error('Register error:', error)
      return false
    }
  }

  // 登出函数
  const logout = () => {
    localStorage.removeItem('access_token')
    setUser(null)
  }

  // 更新用户信息
  const updateUser = (userData: Partial<User>) => {
    if (user) {
      setUser({ ...user, ...userData })
    }
  }

  // 刷新用户信息
  const refreshUser = async (): Promise<void> => {
    try {
      const token = getToken()
      if (token) {
        const freshUser = await AuthAPI.getCurrentUser()
        setUser(freshUser)
        // 不返回用户信息，保持void返回类型
      }
    } catch (error) {
      console.error('Refresh user error:', error)
      throw error // 抛出错误让调用者知道刷新失败
    }
  }

  // 检查认证状态
  const checkAuth = async () => {
    try {
      const token = getToken()
      
      if (!token) {
        setIsLoading(false)
        return
      }
      
      // 如果有token，立即将isAuthenticated设为true
      // 这样用户可以立即访问受保护页面，然后我们异步获取用户信息
      // 先设置一个临时用户对象，确保isAuthenticated为true
      setUser({ id: 0, email: '', is_active: true, created_at: new Date().toISOString() })
      setIsLoading(false)
      
      // 异步获取用户信息
      try {
        const user = await AuthAPI.getCurrentUser()
        setUser(user)
      } catch (error) {
        console.error('Failed to fetch user info:', error)
        // 这里不再清除token，因为它可能在后续请求中有效
        // 只在绝对确定token无效时才清除
        // 注意：保持临时用户对象，确保isAuthenticated保持为true
      }
    } catch (error) {
      console.error('Auth check error:', error)
      setIsLoading(false)
    }
  }

  // 组件挂载时检查认证状态
  useEffect(() => {
    checkAuth()
  }, [])

  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout,
    updateUser,
    refreshUser,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// 使用认证的Hook
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}