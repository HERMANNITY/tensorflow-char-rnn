import argparse
import logging
import os
import shutil
import sys

from char_rnn_model import *

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_file', type=str,
                        default='data/tiny_shakespeare.txt',
                        help='data file')
    parser.add_argument('--save', type=str, default='saved_model/model',
                        help='directory and prefix to store checkpointed models')
    parser.add_argument('--save_best_model', type=str, default='best_model/model',
                        help='directory and prefix to store the best model')
    parser.add_argument('--hidden_size', type=int, default=128,
                        help='size of RNN hidden states')
    parser.add_argument('--embedding_size', type=int, default=50,
                        help='size of character embeddings')
    parser.add_argument('--num_layers', type=int, default=2,
                        help='number of layers in the RNN')
    parser.add_argument('--batch_size', type=int, default=20,
                        help='minibatch size')
    parser.add_argument('--num_unrollings', type=int, default=10,
                        help='number of unrolling steps.')
    parser.add_argument('--num_epochs', type=int, default=50,
                        help='number of epochs')
    # parser.add_argument('--save_freq', type=int, default=1000,
    #                     help='frequency of model saving')
    parser.add_argument('--max_grad_norm', type=float, default=5.,
                        help='clip global grad norm')
    parser.add_argument('--learning_rate', type=float, default=2e-3,
                        help='initial learning rate')
    parser.add_argument('--decay_rate', type=float, default=0.95,
                        help='decay rate for rmsprop')
    parser.add_argument('--log_file', type=str,
                        default='stdout',
                        help='output experiment logs to stdout or a file')
    parser.add_argument('--tb_log_dir', type=str,
                        default='tensorboard_log',
                        help=('directory to store logs for tensorboard',
                              ' visualization'))
    parser.add_argument('--init_model', type=str,
                        default='',
                        help=('initial model'))
    parser.add_argument('--best_model', type=str,
                        default='',
                        help=('current best model'))
    parser.add_argument('--best_valid_ppl', type=float,
                        default='',
                        help=('current valid perplexity'))
    parser.add_argument('--progress_freq', type=int,
                        default=100,
                        help=('frequency for progress report in training',
                              ' and evalution.'))
    parser.add_argument('--verbose', type=int,
                        default=0,
                        help=('whether to show progress report in training',
                              ' and evalution.'))

    parser.add_argument('--test', dest='test', action='store_true')
    parser.set_defaults(test=False)

    parser.add_argument('--keep_tb_log', dest='keep_tb_log', action='store_true')
    parser.set_defaults(keep_tb_log=False)

    parser.add_argument('--sample', dest='sample', action='store_true')
    parser.set_defaults(sample=False)

    parser.add_argument('--max_prob', dest='max_prob', action='store_true')
    parser.set_defaults(max_prob=False)
    
    parser.add_argument('--start_text', type=str,
                        default='The ',
                        help='the text to start with')

    parser.add_argument('--length', type=int,
                        default=100,
                        help='length of sampled sequence')

    parser.add_argument('--evaluate', dest='evaluate', action='store_true')
    parser.set_defaults(evaluate=False)

    parser.add_argument('--example_text', type=str,
                        default='The meaning of life is 42.',
                        help='compute the perplexity of given example text.')
    
    parser.add_argument('--debug', dest='debug', action='store_true')
    parser.set_defaults(debug=False)
    
    args = parser.parse_args()

    if args.log_file == 'stdout':
        logging.basicConfig(stream=sys.stdout,
                            format='%(asctime)s %(levelname)s:%(message)s', 
                            level=logging.INFO,
                            datefmt='%I:%M:%S')
    else:
        logging.basicConfig(filename=args.log_file,
                            format='%(asctime)s %(levelname)s:%(message)s', 
                            level=logging.INFO,
                            datefmt='%I:%M:%S')

    print('all information logged to %s' % args.log_file)

    logging.info('Reading data from: %s', args.data_file)
    with open(args.data_file, 'r') as f:
        text = f.read()
    if args.test:
        text = text[:1000]
    logging.info('number of characters: %s', len(text))
    n = 10
    logging.info('first %d characters: %s', n, text[:n])

    logging.info('Creating train, valid, test split')
    train_size = int(0.8 * len(text))
    valid_size = int(0.1 * len(text))
    test_size = len(text) - train_size - valid_size
    train_text = text[:train_size]
    valid_text = text[train_size:train_size + valid_size]
    test_text = text[train_size + valid_size:]

    logging.info('Creating vocabulary')
    unique_chars = list(set(text))
    vocab_size = len(unique_chars)
    logging.info('vocab size: %d', vocab_size)
    vocab_index_dict = {}
    index_vocab_dict = {}
    for i, char in enumerate(unique_chars):
        vocab_index_dict[char] = i
        index_vocab_dict[i] = char

    # Prepare parameters
    params = {'batch_size': args.batch_size,
              'num_unrollings': args.num_unrollings,
              'vocab_size': vocab_size,
              'hidden_size': args.hidden_size,
              'max_grad_norm': args.max_grad_norm,
              'embedding_size': args.embedding_size, 
              'num_layers': args.num_layers,
              'learning_rate': args.learning_rate}

    # Create batch generators
    batch_size = params['batch_size']
    num_unrollings = params['num_unrollings']
    train_batches = BatchGenerator(train_text, batch_size, num_unrollings, vocab_size, 
                                   vocab_index_dict, index_vocab_dict)
    eval_train_batches = BatchGenerator(train_text, 1, 1, vocab_size,
                                        vocab_index_dict, index_vocab_dict)
    valid_batches = BatchGenerator(valid_text, 1, 1, vocab_size,
                                   vocab_index_dict, index_vocab_dict)
    test_batches = BatchGenerator(test_text, 1, 1, vocab_size,
                                  vocab_index_dict, index_vocab_dict)

    if args.debug:
        logging.info('Test batch generators')
        logging.info(batches2string(train_batches.next(), index_vocab_dict))
        logging.info(batches2string(valid_batches.next(), index_vocab_dict))
        logging.info('Show vocabulary')
        logging.info(vocab_index_dict)
        logging.info(index_vocab_dict)
        
    # Create graphs
    logging.info('Creating graph')
    graph = tf.Graph()
    with graph.as_default():
        with tf.name_scope('training'):
            train_model = CharRNN(is_training=True, **params)
        tf.get_variable_scope().reuse_variables()
        with tf.name_scope('evaluation'):
            valid_model = CharRNN(is_training=False, **params)

    if args.sample:
        # Sampling a sequence 
        with tf.Session(graph=graph) as session:
            train_model.saver.restore(session, args.init_model)
            sample = valid_model.sample_seq(session, args.length, args.start_text,
                                            vocab_index_dict, index_vocab_dict,
                                            max_prob=args.max_prob)
            print('\nstart text is:\n%s' % args.start_text)
            print('sampled text is:\n%s' % sample)
        return sample
    elif args.evaluate:
        example_batches = BatchGenerator(args.example_text, 1, 1, vocab_size,
                                         vocab_index_dict, index_vocab_dict)
        with tf.Session(graph=graph) as session:
            train_model.saver.restore(session, args.init_model)
            ppl = valid_model.run_epoch(session, len(args.example_text),
                                        example_batches,
                                        is_training=False)[0]
            print('\nexample text is: %s' % args.example_text)
            print('its perplexity is: %s' % ppl)
        return ppl
        
            
    logging.info('Start training')
    logging.info('model size (number of parameters): %s', train_model.model_size)
    
    if os.path.exists(args.tb_log_dir) and (not args.keep_tb_log):
        shutil.rmtree(args.tb_log_dir)

    # create new folders if the save directory doesn't exist.
    save_dir = os.path.split(args.save)[0]
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    save_dir = os.path.split(args.save_best_model)[0]
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    if args.best_model:
        best_model = args.best_model
        best_valid_ppl = args.best_valid_ppl
    else:
        best_model = ''
        
    with tf.Session(graph=graph) as session:
        writer = tf.train.SummaryWriter(args.tb_log_dir, session.graph_def)
        # load a saved model or start from random initialization.
        if args.init_model:
            train_model.saver.restore(session, args.init_model)
        else:
            tf.initialize_all_variables().run()
        for i in range(args.num_epochs):
            logging.info('\n')
            logging.info('Epoch %d\n', i)
            logging.info('Training on training set')
            # training step
            ppl, train_summary_str, global_step = train_model.run_epoch(
                session,
                train_size,
                train_batches,
                is_training=True,
                verbose=args.verbose,
                freq=args.progress_freq)
            # record the summary
            writer.add_summary(train_summary_str, global_step)
            # save model
            saved_path = train_model.saver.save(session, args.save,
                                                global_step=train_model.global_step)
            logging.info('model saved in %s\n', saved_path)
            logging.info('Evaluate on validation set')
            valid_ppl, valid_summary_str, _ = valid_model.run_epoch(
                session,
                valid_size,
                valid_batches, 
                is_training=False,
                verbose=args.verbose,
                freq=args.progress_freq)
            # save and update best model
            if (not best_model) or (valid_ppl < best_valid_ppl):
                best_model = train_model.best_model_saver.save(
                    session,
                    args.save_best_model,
                    global_step=train_model.global_step)
                best_valid_ppl = valid_ppl
            writer.add_summary(valid_summary_str, global_step)
            writer.flush()
            logging.info('best model is saved in %s', best_model)
            logging.info('best validation ppl is %f\n', best_valid_ppl)

        logging.info('latest model is saved in %s', saved_path)
        logging.info('best model is saved in %s', best_model)
        logging.info('best validation ppl is %f\n', best_valid_ppl)
        logging.info('Evaluate the best model on test set')
        train_model.saver.restore(session, best_model)
        valid_model.run_epoch(session, test_size, test_batches,
                              is_training=False,
                              verbose=args.verbose,
                              freq=args.progress_freq)
        return best_model


if __name__ == '__main__':
    main()