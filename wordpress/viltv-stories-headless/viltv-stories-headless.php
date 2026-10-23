<?php
/**
 * Plugin Name: VilfinTV Stories Headless
 * Description: Editorial story and chapter post types with a safe, versioned static JSON exporter.
 * Version: 0.1.0
 */
if (!defined('ABSPATH')) exit;
add_action('init', function () {
  register_post_type('viltv_story', [
    'label'=>'VilfinTV Stories', 'public'=>false, 'show_ui'=>true,
    'show_in_rest'=>true, 'supports'=>['title','editor','excerpt','thumbnail','custom-fields']
  ]);
  register_post_type('viltv_chapter', [
    'label'=>'VilfinTV Chapters', 'public'=>false, 'show_ui'=>true,
    'show_in_rest'=>true, 'supports'=>['title','editor','page-attributes','custom-fields']
  ]);
  register_taxonomy('viltv_genre','viltv_story', [
    'label'=>'Genres','public'=>false,'show_ui'=>true,'show_in_rest'=>true,'hierarchical'=>true
  ]);
});
function viltv_export_stories($directory) {
  if (!is_dir($directory) && !wp_mkdir_p($directory)) throw new RuntimeException('Cannot create export directory');
  $items=[];
  $stories=get_posts(['post_type'=>'viltv_story','post_status'=>'publish','numberposts'=>-1,'orderby'=>'title','order'=>'ASC']);
  foreach ($stories as $story) {
    $chapters=get_posts(['post_type'=>'viltv_chapter','post_status'=>'publish','numberposts'=>-1,'meta_key'=>'viltv_story_id','meta_value'=>$story->ID,'orderby'=>'menu_order','order'=>'ASC']);
    $chapter_data=[];
    foreach ($chapters as $i=>$chapter) {
      $body=wp_strip_all_tags(strip_shortcodes($chapter->post_content),true);
      $paras=array_values(array_filter(array_map('trim',preg_split('/\\R{2,}/u',$body))));
      if (!$paras) continue;
      $chapter_data[]=['id'=>'chapter-'.$chapter->ID,'number'=>count($chapter_data)+1,'title'=>sanitize_text_field($chapter->post_title),'paragraphs'=>$paras];
    }
    if (!$chapter_data) continue;
    $slug=sanitize_title($story->post_name);
    $genres=wp_get_post_terms($story->ID,'viltv_genre',['fields'=>'slugs']);
    if (is_wp_error($genres) || !$genres) $genres=['general'];
    $levels=get_post_meta($story->ID,'viltv_levels',true);
    if (!is_array($levels) || !$levels) $levels=['general'];
    $levels=array_values(array_intersect(['kids','general','expert'],$levels));
    if (!$levels) $levels=['general'];
    $payload=[
      'schemaVersion'=>1,'id'=>'wp-'.$story->ID,'slug'=>$slug,
      'title'=>sanitize_text_field($story->post_title),
      'synopsis'=>sanitize_textarea_field($story->post_excerpt),
      'revision'=>get_post_modified_time('YmdHis',true,$story),
      'genreIds'=>array_values(array_map('sanitize_title',$genres)),
      'levels'=>$levels,'chapters'=>$chapter_data
    ];
    $json=wp_json_encode($payload,JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT);
    if (!$json || file_put_contents($directory.'/'.$slug.'.json',$json,LOCK_EX)===false) throw new RuntimeException('Export failed: '.$slug);
    $items[]=['id'=>$payload['id'],'slug'=>$slug,'title'=>$payload['title'],'synopsis'=>$payload['synopsis'],'genreIds'=>$payload['genreIds'],'levels'=>$levels,'chapterCount'=>count($chapter_data),'revision'=>$payload['revision']];
  }
  $index=['schemaVersion'=>1,'generatedAt'=>gmdate('c'),'stories'=>$items];
  if (file_put_contents($directory.'/index.json',wp_json_encode($index,JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT),LOCK_EX)===false) throw new RuntimeException('Index export failed');
  return count($items);
}
if (defined('WP_CLI') && WP_CLI) {
  WP_CLI::add_command('viltv stories-export',function ($args,$assoc) {
    $dir=isset($assoc['dir'])?$assoc['dir']:WP_CONTENT_DIR.'/uploads/viltv-export';
    $count=viltv_export_stories($dir);
    WP_CLI::success("Exported $count published stories to $dir. Review generated JSON before deployment.");
  });
}
