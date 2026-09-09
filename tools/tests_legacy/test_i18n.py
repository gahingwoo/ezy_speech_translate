#!/usr/bin/env python3
"""
多语言 (I18n) 测试脚本
Test script for bilingual (I18n) functionality
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ezy_manager import I18n, Colors

def test_chinese():
    """测试中文"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== 中文测试 (Chinese Test) ==={Colors.ENDC}\n")
    
    I18n.set_language('zh')
    
    print(f"{Colors.OKBLUE}{I18n.t('installing_packages')}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{I18n.t('install_packages_success')}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{I18n.t('creating_service_user', 'ezyspeech')}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{I18n.t('service_user_created', 'ezyspeech')}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{I18n.t('copying_application', '/opt/ezy_speech_translate')}{Colors.ENDC}")
    print(f"{Colors.WARNING}{I18n.t('selinux_enforcing')}{Colors.ENDC}")
    print(f"{Colors.HEADER}第1步: {I18n.t('step_validation')}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{I18n.t('services_started')}{Colors.ENDC}")
    print()

def test_english():
    """测试英文"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== English Test ==={Colors.ENDC}\n")
    
    I18n.set_language('en')
    
    print(f"{Colors.OKBLUE}{I18n.t('installing_packages')}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{I18n.t('install_packages_success')}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{I18n.t('creating_service_user', 'ezyspeech')}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{I18n.t('service_user_created', 'ezyspeech')}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{I18n.t('copying_application', '/opt/ezy_speech_translate')}{Colors.ENDC}")
    print(f"{Colors.WARNING}{I18n.t('selinux_enforcing')}{Colors.ENDC}")
    print(f"{Colors.HEADER}Step 1: {I18n.t('step_validation')}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{I18n.t('services_started')}{Colors.ENDC}")
    print()

if __name__ == '__main__':
    test_chinese()
    test_english()
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ I18n 测试完成 (I18n test complete)!{Colors.ENDC}\n")
