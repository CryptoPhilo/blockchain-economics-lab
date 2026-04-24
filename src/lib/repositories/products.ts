import { SupabaseClient } from '@supabase/supabase-js'
import type { BundleItem, Category, Product } from '../types'
import { filterPublicProducts, isProductPubliclyAvailable } from '@/lib/product-access'

export class ProductsRepository {
  constructor(private supabase: SupabaseClient) {}

  async getCategories() {
    const { data, error } = await this.supabase
      .from('categories')
      .select('*')
      .order('sort_order')

    if (error) {
      throw new Error(`Failed to fetch categories: ${error.message}`)
    }

    return (data || []) as Category[]
  }

  async getFeaturedProducts(limit = 4) {
    const { data, error } = await this.supabase
      .from('products')
      .select('*, category:categories(*)')
      .eq('status', 'published')
      .eq('featured', true)
      .order('published_at', { ascending: false })
      .limit(limit)

    if (error) {
      throw new Error(`Failed to fetch featured products: ${error.message}`)
    }

    return filterPublicProducts((data || []) as Product[])
  }

  async getPublishedProducts(params: { type?: string; categorySlug?: string } = {}) {
    const { type, categorySlug } = params

    let categoryId: string | undefined
    if (categorySlug) {
      const { data: category, error: categoryError } = await this.supabase
        .from('categories')
        .select('id')
        .eq('slug', categorySlug)
        .maybeSingle()

      if (categoryError) {
        throw new Error(`Failed to resolve category: ${categoryError.message}`)
      }

      if (!category) {
        return []
      }

      categoryId = category.id
    }

    let query = this.supabase
      .from('products')
      .select('*, category:categories(*)')
      .eq('status', 'published')
      .order('featured', { ascending: false })
      .order('published_at', { ascending: false })

    if (type) {
      query = query.eq('type', type)
    }

    if (categoryId) {
      query = query.eq('category_id', categoryId)
    }

    const { data, error } = await query

    if (error) {
      throw new Error(`Failed to fetch products: ${error.message}`)
    }

    return filterPublicProducts((data || []) as Product[])
  }

  async getProductBySlug(slug: string) {
    const { data, error } = await this.supabase
      .from('products')
      .select('*, category:categories(*)')
      .eq('slug', slug)
      .eq('status', 'published')
      .maybeSingle()

    if (error) {
      throw new Error(`Failed to fetch product: ${error.message}`)
    }

    if (!data || !isProductPubliclyAvailable(data as Product)) {
      return null
    }

    return data as Product | null
  }

  async getBundleItems(bundleId: string) {
    const { data, error } = await this.supabase
      .from('bundle_items')
      .select('*, product:products(*, category:categories(*))')
      .eq('bundle_id', bundleId)
      .order('sort_order')

    if (error) {
      throw new Error(`Failed to fetch bundle items: ${error.message}`)
    }

    return (data || []) as BundleItem[]
  }
}

export function createProductsRepository(supabase: SupabaseClient) {
  return new ProductsRepository(supabase)
}
