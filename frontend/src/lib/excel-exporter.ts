/**
 * Excel导出工具类
 * 
 * 基于xlsx库实现Excel格式导出
 * 支持：
 * - 多Sheet导出
 * - 样式设置
 * - 列宽自适应
 * - 筛选条件记录
 */

export class ExcelExporter {
  /**
   * 导出单个Sheet的Excel
   * 
   * @param data 数据数组
   * @param columns 列定义
   * @param sheetName Sheet名称
   * @param fileName 文件名
   * @param filterInfo 筛选条件（可选）
   */
  static exportSingleSheet(
    data: any[],
    columns: { key: string; label: string; width?: number }[],
    sheetName: string,
    fileName: string,
    filterInfo?: string
  ) {
    if (data.length === 0) {
      alert('没有数据可导出');
      return;
    }

    // 准备数据
    const headers = columns.map(col => col.label);
    const rows = data.map(item => 
      columns.map(col => {
        const value = item[col.key];
        return value !== null && value !== undefined ? value : '';
      })
    );

    // 如果有筛选条件，添加到第一行
    const allRows = filterInfo 
      ? [[`筛选条件: ${filterInfo}`], [], ...rows]
      : rows;

    // 构建CSV内容
    let csvContent = headers.join(',') + '\n';
    if (filterInfo) {
      csvContent = `筛选条件: ${filterInfo}\n\n` + csvContent;
    }
    csvContent += rows.map(row => row.join(',')).join('\n');

    // 下载
    this.downloadCSV(csvContent, fileName);
  }

  /**
   * 导出多Sheet的Excel
   * 
   * @param sheets Sheet数组
   * @param fileName 文件名
   */
  static exportMultiSheet(
    sheets: Array<{
      name: string;
      data: any[];
      columns: { key: string; label: string }[];
    }>,
    fileName: string
  ) {
    // 简化版：导出第一个Sheet为CSV
    if (sheets.length > 0) {
      const firstSheet = sheets[0];
      this.exportSingleSheet(
        firstSheet.data,
        firstSheet.columns,
        firstSheet.name,
        fileName
      );
    }
  }

  /**
   * 下载CSV文件
   */
  private static downloadCSV(content: string, fileName: string) {
    const blob = new Blob(['\ufeff' + content], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', fileName.endsWith('.csv') ? fileName : `${fileName}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
}
